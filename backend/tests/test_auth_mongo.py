"""Opt-in real database checks for sessions and authenticated ownership.

Only randomly named pdw_test_* databases are created/removed. Provider calls are
faked inside the test process; there is no mock identity endpoint in the app.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app import auth_api
from backend.app.auth_provider import AuthSettings
from backend.app.identity import IdentityStore,digest
from backend.app.repositories import MongoRepository
from backend.app.storage_api import repository
from backend.app.workspaces import StorageError
from backend.tests.test_storage import state_fixture


class TestProvider:
    config=AuthSettings('example.auth0.com','client','secret','machine','machine-secret')
    def __init__(self):self.profiles={}
    def profile(self,subject):return self.profiles[subject]
    async def login(self,request,signup=False):
        from starlette.responses import RedirectResponse
        request.session['test_nonce']='n'
        return RedirectResponse('https://example.auth0.com/authorize')
    async def claims(self,request):
        if request.session.get('test_nonce')!='n':raise ValueError('Flow missing')
        return {'sub':'auth0|a','auth_time':int(time.time())}


@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI to run real Mongo account tests.')
class MongoAccountTests(unittest.TestCase):
    def setUp(self):
        from pymongo import MongoClient
        self.client=MongoClient(os.environ['PDW_TEST_MONGO_URI'],serverSelectionTimeoutMS=2000,tz_aware=True)
        self.database_name='pdw_test_'+uuid4().hex
        database=self.client[self.database_name]
        self.store=IdentityStore(database)
        self.repo=MongoRepository(database)
        self.source=TestProvider()
        self.tokens={}
        for key in ('a','b','unverified'):
            self.source.profiles['auth0|'+key]={'user_id':'auth0|'+key,'email':key+'@example.com','email_verified':key!='unverified'}
            self.tokens[key]=self.store.create_session(self.source.config.issuer,'auth0|'+key,key+'@example.com',key!='unverified',time.time())
        self.patches=[patch.dict(os.environ,{'PDW_AUTH_MODE':'auth0','PDW_LOCAL_STORAGE':'1','PDW_APP_ORIGIN':'http://127.0.0.1:5173'}),
            patch.object(auth_api,'identity_store',return_value=self.store),patch.object(auth_api,'provider',return_value=self.source)]
        for item in self.patches:item.start()
        app.dependency_overrides[repository]=lambda:self.repo
        self.web=TestClient(app)
    def tearDown(self):
        self.web.close();app.dependency_overrides.clear()
        for item in self.patches:item.stop()
        self.client.drop_database(self.database_name);self.client.close()
    def authenticate(self,key='a'):
        token=self.tokens[key];self.web.cookies.set(auth_api.SESSION_COOKIE,token)
        return {'X-PDW-CSRF':self.store.session(token)[0]['csrf']}
    def create(self):
        result=self.web.post('/api/v1/decisions',headers=self.authenticate(),json={'request_id':str(uuid4()),'state':state_fixture()})
        self.assertEqual(result.status_code,201,result.text)
        return result.json()
    def test_accounts_cannot_access_each_others_workspaces_or_reviews(self):
        saved=self.create();path='/api/v1/decisions/'+saved['id']
        review=self.web.post(path+'/snapshots',headers=self.authenticate(),json={'expected_revision':1,'request_id':str(uuid4())})
        self.assertEqual(review.status_code,201,review.text)
        headers=self.authenticate('b')
        self.assertEqual(self.web.get('/api/v1/decisions').json()['items'],[])
        self.assertEqual(self.web.get(path).status_code,404)
        self.assertEqual(self.web.patch(path,headers=headers,json={'expected_revision':1,'state':state_fixture()}).status_code,404)
        self.assertEqual(self.web.get(path+'/snapshots/'+review.json()['id']).status_code,404)
    def test_unverified_user_cannot_save(self):
        result=self.web.post('/api/v1/decisions',headers=self.authenticate('unverified'),json={'request_id':str(uuid4()),'state':state_fixture()})
        self.assertEqual(result.status_code,403)
    def test_verification_refresh_unlocks_only_that_user(self):
        self.authenticate('unverified')
        self.assertFalse(self.web.get('/api/v1/auth/session').json()['verified'])
        self.source.profiles['auth0|unverified']['email_verified']=True
        self.assertTrue(self.web.get('/api/v1/auth/session').json()['verified'])
    def test_password_reset_revokes_older_sessions(self):
        from datetime import datetime,timezone
        self.authenticate()
        self.source.profiles['auth0|a']['last_password_reset']=datetime.now(timezone.utc).isoformat()
        self.assertEqual(self.web.get('/api/v1/decisions').status_code,401)
        self.assertIsNone(self.store.sessions.find_one({'_id':digest(self.tokens['a'])}))
    def test_fresh_signup_and_same_second_password_reset(self):
        from datetime import datetime,timezone
        second=int(time.time())
        initial=datetime.fromtimestamp(second+0.010,timezone.utc).isoformat()
        changed=datetime.fromtimestamp(second+0.020,timezone.utc).isoformat()
        self.source.profiles['auth0|a']['last_password_reset']=initial
        token=self.store.create_session(self.source.config.issuer,'auth0|a','a@example.com',True,second,password_changed_at=initial)
        self.web.cookies.set(auth_api.SESSION_COOKIE,token)
        self.assertEqual(self.web.get('/api/v1/decisions').status_code,200)
        self.source.profiles['auth0|a']['last_password_reset']=changed
        self.assertEqual(self.web.get('/api/v1/decisions').status_code,401)

    def test_logout_revokes_cookie_but_preserves_saved_records(self):
        saved=self.create();headers=self.authenticate()
        record,user=self.store.session(self.tokens['a'])
        self.assertEqual(self.web.post('/api/v1/auth/logout',headers=headers,json={}).status_code,200)
        self.assertEqual(self.repo.get(user['_id'],saved['id'])['revision'],1)
        with self.assertRaises(StorageError):self.store.session(self.tokens['a'])
    def test_expiry_checked_even_before_ttl_cleanup(self):
        self.authenticate()
        self.store.sessions.update_one({'_id':digest(self.tokens['a'])},{'$set':{'last_active':time.time()-3600}})
        self.assertEqual(self.web.get('/api/v1/decisions').status_code,401)
    def test_oauth_flow_can_be_consumed_only_once(self):
        flow=self.store.create_flow();self.store.save_flow(flow,{'nonce':'test'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.store.consume_flow(flow),range(2)))
        self.assertEqual(sum(bool(result) for result in results),1)
    def test_flow_cookie_binding_replay_and_session_cookie_flags(self):
        response=self.web.get('/api/v1/auth/login',follow_redirects=False)
        self.assertEqual(response.status_code,307,response.text)
        flow=self.web.cookies.get(auth_api.FLOW_COOKIE)
        self.assertTrue(flow)
        anonymous=TestClient(app)
        try:
            rejected=anonymous.get('/api/v1/auth/callback?code=demo',follow_redirects=False)
            self.assertIn('signin_failed',rejected.headers['location'])
        finally:anonymous.close()
        accepted=self.web.get('/api/v1/auth/callback?code=demo',follow_redirects=False)
        self.assertEqual(accepted.status_code,303)
        self.assertNotIn('signin_failed',accepted.headers['location'])
        cookie=accepted.headers.get_list('set-cookie')[0]
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=lax',cookie)
        self.web.cookies.set(auth_api.FLOW_COOKIE,flow,path='/api/v1/auth')
        replay=self.web.get('/api/v1/auth/callback?code=demo',follow_redirects=False)
        self.assertIn('signin_failed',replay.headers['location'])
    def test_local_demo_records_are_not_assigned_to_first_account(self):
        decision=str(uuid4());self.repo.create('local-development-user',decision,state_fixture())
        self.authenticate()
        self.assertEqual(self.web.get('/api/v1/decisions/'+decision).status_code,404)
    def test_pending_deletion_state_denies_ordinary_access(self):
        self.authenticate();_,user=self.store.session(self.tokens['a'])
        self.store.users.update_one({'_id':user['_id']},{'$set':{'state':'pending_deletion'}})
        self.assertEqual(self.web.get('/api/v1/decisions').status_code,403)
