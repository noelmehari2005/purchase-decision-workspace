"""Account boundaries, session clocks, CSRF, and account-to-workspace isolation."""
from copy import deepcopy
import logging
import os
import time
import unittest
from unittest.mock import MagicMock,patch
from types import SimpleNamespace

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app import auth_api
from backend.app.auth_provider import AuthSettings,settings
from backend.app.identity import IdentityStore,digest
from backend.app.storage_api import repository
from backend.app.workspaces import StorageError
from backend.tests.test_storage import MemoryRepository,state_fixture


class SessionRules(unittest.TestCase):
    def setUp(self):
        self.db=MagicMock()
        self.store=IdentityStore(self.db)
        self.user={'_id':'owner-a','state':'active','subject':'auth0|a','email':'a@example.com','email_verified':True}
        self.record={'_id':digest('cookie-a'),'owner_id':'owner-a','created_at':100,'auth_time':99,
                     'last_active':100,'absolute_until':86500,'csrf':'csrf-a'}
        self.db.app_sessions.find_one.return_value=self.record
        self.db.users.find_one.return_value=self.user
    def test_idle_boundary_expires_without_waiting(self):
        self.assertEqual(self.store.session('cookie-a',clock=3699)[1],self.user)
        with self.assertRaises(StorageError) as raised:self.store.session('cookie-a',clock=3700)
        self.assertEqual(raised.exception.code,'session_expired')
        self.db.app_sessions.delete_one.assert_called_with({'_id':digest('cookie-a')})
    def test_absolute_expiry_even_with_recent_activity(self):
        self.record['last_active']=86499
        with self.assertRaises(StorageError):self.store.session('cookie-a',clock=86500)
    def test_fresh_signup_accepts_millisecond_password_timestamp(self):
        token=self.store.create_session('https://example.auth0.com/','auth0|a','a@example.com',True,
            100,clock=100.5,password_changed_at='1970-01-01T00:01:40.010Z')
        stored=self.db.app_sessions.insert_one.call_args.args[0]
        profile={'user_id':'auth0|a','email':'a@example.com','email_verified':True,
                 'last_password_reset':'1970-01-01T00:01:40.010Z'}
        self.assertTrue(self.store.refresh_profile(self.user,profile,stored)['email_verified'])
        self.assertEqual(stored['_id'],digest(token))

    def test_later_password_change_in_same_second_revokes_session(self):
        self.record['credential_version']=100.010
        profile={'user_id':'auth0|a','email':'a@example.com','email_verified':True,
                 'last_password_reset':'1970-01-01T00:01:40.020Z'}
        with self.assertRaises(StorageError) as raised:self.store.refresh_profile(self.user,profile,self.record)
        self.assertEqual(raised.exception.code,'session_revoked')

    def test_token_from_before_password_change_cannot_start_new_session(self):
        with self.assertRaises(StorageError):
            self.store.create_session('https://example.auth0.com/','auth0|a','a@example.com',True,
                99,clock=101,password_changed_at='1970-01-01T00:01:40.010Z')
        self.db.app_sessions.insert_one.assert_not_called()

    def test_missing_session_and_restricted_user_denied(self):
        self.db.app_sessions.find_one.return_value=None
        with self.assertRaises(StorageError):self.store.session('unknown',clock=100)
        self.db.app_sessions.find_one.return_value=self.record
        self.user['state']='pending_deletion'
        with self.assertRaises(StorageError) as raised:self.store.session('cookie-a',clock=100)
        self.assertEqual(raised.exception.code,'account_restricted')
    def test_session_checks_do_not_extend_idle(self):
        self.store.session('cookie-a',clock=101)
        self.db.app_sessions.update_one.assert_not_called()
    def test_touch_cannot_revive_revoked_session(self):
        self.db.app_sessions.update_one.return_value=SimpleNamespace(matched_count=0)
        with self.assertRaises(StorageError):self.store.touch('cookie-a',clock=101)
        query=self.db.app_sessions.update_one.call_args.args[0]
        self.assertEqual(query['last_active'],{'$gt':-3499})
    def test_password_reset_revokes_all_older_authentications(self):
        profile={'user_id':'auth0|a','email':'a@example.com','email_verified':True,
                 'last_password_reset':'1970-01-01T00:01:40+00:00'}
        with self.assertRaises(StorageError) as raised:self.store.refresh_profile(self.user,profile,self.record)
        self.assertEqual(raised.exception.code,'session_revoked')
        self.db.app_sessions.delete_many.assert_called_with({'owner_id':'owner-a','credential_version':{'$ne':100.0}})
    def test_invalid_password_reset_timestamp_fails_closed(self):
        for value in ['not-a-date','2026-01-01T00:00:00',42]:
            with self.subTest(value=value),self.assertRaises(StorageError) as raised:
                self.store.refresh_profile(self.user,{'user_id':'auth0|a','last_password_reset':value},self.record)
            self.assertEqual(raised.exception.status,503)

    def test_new_login_after_reset_is_allowed(self):
        self.record['auth_time']=101
        self.record['credential_version']=100.0
        profile={'user_id':'auth0|a','email':'a@example.com','email_verified':True,
                 'last_password_reset':'1970-01-01T00:01:40+00:00'}
        self.assertTrue(self.store.refresh_profile(self.user,profile,self.record)['email_verified'])
    def test_profile_ownership_and_verification_are_not_coerced(self):
        with self.assertRaises(StorageError):self.store.refresh_profile(self.user,{'user_id':'auth0|other'},self.record)
        profile={'user_id':'auth0|a','email':'a@example.com','email_verified':'true'}
        self.assertFalse(self.store.refresh_profile(self.user,profile,self.record)['email_verified'])
    def test_flow_is_consumed_once_and_expiry_is_checked(self):
        self.db.login_flows.find_one_and_delete.return_value={'data':{'nonce':'n'},'until':200}
        self.assertEqual(self.store.consume_flow('flow',clock=199),{'nonce':'n'})
        self.assertEqual(self.store.consume_flow('flow',clock=200),{})
        self.db.login_flows.find_one_and_delete.assert_called_with({'_id':digest('flow')})
    def test_raw_session_cookie_is_not_stored(self):
        token=self.store.create_session('https://example.auth0.com/','auth0|a','a@example.com',True,99,clock=100)
        stored=self.db.app_sessions.insert_one.call_args.args[0]
        self.assertEqual(stored['_id'],digest(token))
        self.assertNotIn(token,str(stored))
        self.assertEqual(stored['absolute_until'],86500)
        self.assertEqual(stored['last_active'],100)


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'PDW_AUTH_MODE':'auth0','PDW_LOCAL_STORAGE':'1','PDW_APP_ORIGIN':'http://127.0.0.1:5173'})
        self.env.start()
        self.repo=MemoryRepository()
        self.store=MagicMock()
        self.source=MagicMock()
        self.source.config=AuthSettings('example.auth0.com','client','secret','machine','machine-secret')
        self.source.profile.side_effect=lambda subject:{'user_id':subject,'email':subject+'@example.com','email_verified':True}
        def session(token):
            if token not in ('a','b','unverified'):raise StorageError(401,'session_required','Sign in first.')
            owner='owner-'+token
            return {'csrf':'csrf-'+token,'owner_id':owner,'last_active':time.time(),'absolute_until':time.time()+86400}, \
                   {'_id':owner,'subject':'auth0|'+token,'email':token+'@example.com','email_verified':token!='unverified'}
        self.store.session.side_effect=session
        self.store.refresh_profile.side_effect=lambda user,profile,record:user
        self.patches=[patch.object(auth_api,'identity_store',return_value=self.store),patch.object(auth_api,'provider',return_value=self.source)]
        for item in self.patches:item.start()
        app.dependency_overrides[repository]=lambda:self.repo
        self.client=TestClient(app)
    def tearDown(self):
        self.client.close();app.dependency_overrides.clear()
        for item in self.patches:item.stop()
        self.env.stop()
    def authenticate(self,identity='a'):
        self.client.cookies.set(auth_api.SESSION_COOKIE,identity)
        return {'X-PDW-CSRF':'csrf-'+identity,'Origin':'http://127.0.0.1:5173'}
    def create(self):
        from uuid import uuid4
        result=self.client.post('/api/v1/decisions',headers=self.authenticate(),json={'request_id':str(uuid4()),'state':state_fixture()})
        self.assertEqual(result.status_code,201,result.text)
        return result.json()
    def test_no_cookie_cannot_access_saved_workspaces(self):
        result=self.client.get('/api/v1/decisions')
        self.assertEqual(result.status_code,401)
        self.assertEqual(self.repo.list('local-development-user',0,20),[])
    def test_unverified_email_cannot_access_saved_workspaces(self):
        self.authenticate('unverified')
        self.assertEqual(self.client.get('/api/v1/decisions').status_code,403)
        result=self.client.get('/api/v1/auth/session').json()
        self.assertTrue(result['authenticated']);self.assertFalse(result['verified'])
    def test_other_account_cannot_read_list_update_or_snapshot(self):
        created=self.create();path='/api/v1/decisions/'+created['id']
        self.authenticate('b')
        self.assertEqual(self.client.get('/api/v1/decisions').json()['items'],[])
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.patch(path,headers={'X-PDW-CSRF':'csrf-b'},json={'expected_revision':1,'state':state_fixture()}).status_code,404)
        self.assertEqual(self.client.get(path+'/snapshots').status_code,404)
        from uuid import uuid4
        self.assertEqual(self.client.post(path+'/snapshots',headers={'X-PDW-CSRF':'csrf-b'},json={'expected_revision':1,'request_id':str(uuid4())}).status_code,404)
    def test_mutation_requires_csrf_and_matching_origin(self):
        self.authenticate()
        self.assertEqual(self.client.post('/api/v1/auth/activity',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/v1/auth/activity',headers={'X-PDW-CSRF':'csrf-a','Origin':'https://evil.example'},json={}).status_code,403)
        self.assertEqual(self.client.post('/api/v1/auth/activity',headers={'X-PDW-CSRF':'csrf-a'},json={}).status_code,200)
    def test_logout_revokes_cookie_and_does_not_delete_saved_records(self):
        created=self.create()
        result=self.client.post('/api/v1/auth/logout',headers={'X-PDW-CSRF':'csrf-a'},json={})
        self.assertEqual(result.status_code,200)
        self.store.revoke.assert_called_with('a')
        self.assertIn('Max-Age=0',result.headers['set-cookie'])
        self.assertEqual(self.repo.get('owner-a',created['id'])['revision'],1)
    def test_session_response_contains_only_own_identity_and_csrf(self):
        self.authenticate();result=self.client.get('/api/v1/auth/session')
        data=result.json()
        self.assertEqual(data['user']['id'],'owner-a')
        self.assertEqual(result.headers['cache-control'],'no-store')
        self.assertNotIn('client_secret',data);self.assertNotIn('access_token',data)
        self.store.touch.assert_not_called()
    def test_provider_outage_does_not_fall_back_to_local_owner(self):
        self.authenticate()
        self.source.profile.side_effect=StorageError(503,'identity_unavailable','Unavailable')
        self.assertEqual(self.client.get('/api/v1/decisions').status_code,503)
    def test_reset_response_neutral_even_if_provider_fails(self):
        first=self.client.post('/api/v1/auth/password-reset',json={'email':'a@example.com'})
        self.source.request_reset.side_effect=RuntimeError('private provider details')
        second=self.client.post('/api/v1/auth/password-reset',json={'email':'missing@example.com'})
        self.assertEqual(first.status_code,202);self.assertEqual(first.json(),second.json())
        self.assertNotIn('private',second.text)
    def test_reset_rate_limit_and_cross_origin(self):
        self.store.rate_limit.side_effect=StorageError(429,'too_many_requests','Wait')
        self.assertEqual(self.client.post('/api/v1/auth/password-reset',json={'email':'a@example.com'}).status_code,429)
        self.assertEqual(self.client.post('/api/v1/auth/password-reset',headers={'Origin':'https://evil.example'},json={'email':'a@example.com'}).status_code,403)
    def test_account_free_evaluator_still_works(self):
        from backend.app.workspaces import WorkspaceState
        payload=WorkspaceState.model_validate(state_fixture()).evaluation_input().model_dump(mode='json')
        self.assertEqual(self.client.post('/api/v1/evaluations',json=payload).status_code,200)


class AuthConfigurationTests(unittest.TestCase):
    def test_missing_configuration_fails_closed_without_a_secret_in_error(self):
        with patch.dict(os.environ,{'PDW_AUTH0_DOMAIN':'','PDW_AUTH0_CLIENT_SECRET':'private'}):
            with self.assertRaises(StorageError) as raised:settings()
            self.assertNotIn('private',raised.exception.message)
    def test_missing_sdk_leaves_demo_available_and_private_access_closed(self):
        values={'PDW_AUTH_MODE':'auth0','PDW_AUTH0_DOMAIN':'example.auth0.com','PDW_APP_ORIGIN':'http://127.0.0.1:5173',
                'PDW_AUTH0_CLIENT_ID':'client','PDW_AUTH0_CLIENT_SECRET':'secret',
                'PDW_AUTH0_MANAGEMENT_CLIENT_ID':'machine','PDW_AUTH0_MANAGEMENT_CLIENT_SECRET':'secret'}
        with patch.dict(os.environ,values),patch('backend.app.auth_provider.configured_provider',side_effect=ImportError('missing')),TestClient(app) as client:
            status=client.get('/api/v1/auth/session')
            self.assertEqual(status.status_code,200)
            self.assertFalse(status.json()['configured'])
            self.assertFalse(status.json()['authenticated'])
            self.assertEqual(client.get('/api/v1/decisions').status_code,503)

    def test_non_auth0_host_or_non_loopback_origin_rejected(self):
        for changes in [{'PDW_AUTH0_DOMAIN':'evil.example'}, {'PDW_AUTH0_DOMAIN':'https://example.auth0.com/'},
                        {'PDW_AUTH0_DOMAIN':'example.auth0.com','PDW_APP_ORIGIN':'https://public.example'}]:
            with patch.dict(os.environ,changes),self.assertRaises(StorageError):settings()
    def test_oauth_callback_query_is_removed_from_access_logs(self):
        record=logging.LogRecord('uvicorn.access',20,'',0,'%s %s %s %s %s',
            ('ip','GET','/api/v1/auth/callback?code=private&state=private','HTTP/1.1',303),None)
        auth_api.AuthLogFilter().filter(record)
        self.assertNotIn('private',record.getMessage())
