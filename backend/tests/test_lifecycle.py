"""Recovery boundaries and private deletion contracts; no real email/provider calls."""
import os
import time
import unittest
from copy import deepcopy
from unittest.mock import MagicMock,patch
from uuid import UUID,uuid4
from backend.app.workspaces import StorageError
from backend.app.lifecycle import AccountLifecycle,fresh,status,RECOVERY_SECONDS
from backend.app import lifecycle_api
from backend.tests import test_auth as auth_helpers

class LifecycleUnitTests(unittest.TestCase):
    def test_fresh_auth_and_exact_recovery_boundary(self):
        fresh({'auth_time':700},clock=1000)
        with self.assertRaises(StorageError):fresh({'auth_time':699},clock=1000)
        user={'state':'pending_deletion','delete_after':1000}
        self.assertTrue(status(user,999)['can_restore']);self.assertFalse(status(user,1000)['can_restore'])
    def test_duplicate_request_does_not_extend_recovery(self):
        db=MagicMock();service=AccountLifecycle(db)
        user={'_id':'a','state':'pending_deletion','delete_after':1000,'deletion_notice':{'status':'queued'}}
        db.users.find_one.return_value=user
        self.assertEqual(service.request(user,uuid4(),clock=100)['delete_after'],1000)
        db.users.find_one_and_update.assert_not_called()
    def test_restore_is_atomic_before_deadline_and_revokes_sessions(self):
        db=MagicMock();service=AccountLifecycle(db);db.users.find_one_and_update.return_value={'state':'active'}
        service.restore({'_id':'a','deletion_id':'request'},clock=1000)
        query=db.users.find_one_and_update.call_args.args[0]
        self.assertEqual(query['state'],'pending_deletion');self.assertEqual(query['delete_after'],{'$gt':1000})
        db.app_sessions.delete_many.assert_called_once_with({'owner_id':'a','lifecycle_version':None})
        db.users.find_one_and_update.return_value=None
        with self.assertRaises(StorageError):service.restore({'_id':'a'},clock=1000)
    def test_missing_smtp_fails_without_sending(self):
        from backend.app.notifications import smtp_send
        with patch.dict(os.environ,{'PDW_SMTP_HOST':'','PDW_SMTP_FROM':''}),patch('smtplib.SMTP_SSL') as smtp:
            with self.assertRaises(StorageError):smtp_send('a@example.com',0,RECOVERY_SECONDS)
            smtp.assert_not_called()
    def test_mail_uses_tls_and_explicit_deadline_without_bearer_recovery_link(self):
        from backend.app.notifications import smtp_send
        with patch.dict(os.environ,{'PDW_SMTP_HOST':'smtp.example.com','PDW_SMTP_FROM':'app@example.com','PDW_SMTP_PORT':'465',
                                     'PDW_APP_ORIGIN':'http://127.0.0.1:5173'}),patch('smtplib.SMTP_SSL') as smtp:
            smtp.return_value.__enter__.return_value.send_message.return_value={}
            smtp_send('a@example.com',0,RECOVERY_SECONDS)
            message=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertIn('January 31, 1970',message.get_content())
            self.assertIn('Signing in alone does not cancel deletion',message.get_content())
            self.assertNotIn('token=',message.get_content())
            self.assertIsNotNone(smtp.call_args.kwargs['context'])

class LifecycleApiTests(unittest.TestCase):
    setUp=auth_helpers.AuthApiTests.setUp
    tearDown=auth_helpers.AuthApiTests.tearDown
    authenticate=auth_helpers.AuthApiTests.authenticate
    def test_fresh_confirmation_and_csrf_before_account_change(self):
        self.authenticate()
        with patch.object(lifecycle_api,'lifecycle') as service:
            bad=self.client.post('/api/v1/account/deletion-request',headers=self.authenticate(),json={'request_id':str(uuid4()),'confirmation':'delete'})
            self.assertEqual(bad.status_code,422);service.assert_not_called()
            missing=self.client.post('/api/v1/account/deletion-request',json={'request_id':str(uuid4()),'confirmation':'DELETE MY ACCOUNT'})
            self.assertEqual(missing.status_code,403);service.assert_not_called()
            service.return_value.request.return_value={'delete_after':time.time()+RECOVERY_SECONDS,'notification_status':'queued'}
            result=self.client.post('/api/v1/account/deletion-request',headers=self.authenticate(),json={'request_id':str(uuid4()),'confirmation':'DELETE MY ACCOUNT'})
            self.assertEqual(result.status_code,200,result.text);self.assertTrue(result.json()['signed_out'])
            self.assertIn('Max-Age=0',result.headers['set-cookie'])
    def test_old_authentication_requires_sign_in_and_anonymous_cannot_restore(self):
        self.assertEqual(self.client.post('/api/v1/account/restore',json={}).status_code,401)
        self.authenticate()
        self.store.session.return_value=None
        self.store.session.side_effect=lambda *a,**k:({'csrf':'csrf-a','auth_time':time.time()-301},{'_id':'a','subject':'auth0|a','email_verified':True,'state':'active'})
        with patch.object(lifecycle_api,'lifecycle') as service:
            result=self.client.post('/api/v1/account/restore',headers={'X-PDW-CSRF':'csrf-a'},json={})
            self.assertEqual(result.status_code,401);self.assertEqual(result.json()['code'],'reauth_required');service.assert_not_called()

@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI for lifecycle integration tests.')
class MongoLifecycleTests(unittest.TestCase):
    def setUp(self):
        from backend.tests.test_auth_mongo import MongoAccountTests
        MongoAccountTests.setUp(self)
        self.lifecycle=AccountLifecycle(self.repo.database)
        self.lifecycle_patch=patch.object(lifecycle_api,'lifecycle',return_value=self.lifecycle);self.lifecycle_patch.start()
    def tearDown(self):
        self.lifecycle_patch.stop()
        from backend.tests.test_auth_mongo import MongoAccountTests
        MongoAccountTests.tearDown(self)
    def authenticate(self,key='a'):
        from backend.app import auth_api
        token=self.tokens[key];self.web.cookies.set(auth_api.SESSION_COOKIE,token)
        return {'X-PDW-CSRF':self.store.session(token,allow_pending=True)[0]['csrf']}
    def create(self):
        from backend.tests.test_auth_mongo import MongoAccountTests
        return MongoAccountTests.create(self)
    def user(self,key='a'):
        return self.store.session(self.tokens[key],allow_pending=True)[1]
    def test_pending_signin_is_recovery_only_and_restore_requires_explicit_action(self):
        saved=self.create();user=self.user();request_id=uuid4()
        result=self.web.post('/api/v1/account/deletion-request',headers=self.authenticate(),json={'request_id':str(request_id),'confirmation':'DELETE MY ACCOUNT'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.repo.get(user['_id'],saved['id'])['revision'],1)
        with self.assertRaises(StorageError):self.store.session(self.tokens['a'])
        self.tokens['a']=self.store.create_session(self.source.config.issuer,'auth0|a','a@example.com',True,time.time())
        headers=self.authenticate();status_result=self.web.get('/api/v1/auth/session')
        self.assertEqual(status_result.status_code,200,status_result.text)
        self.assertEqual(status_result.json()['account_state'],'pending_deletion')
        self.assertEqual(self.web.get('/api/v1/decisions').status_code,403)
        self.assertEqual(self.web.get('/api/v1/account/export').status_code,403)
        restored=self.web.post('/api/v1/account/restore',headers=headers,json={})
        self.assertEqual(restored.status_code,200,restored.text)
        self.assertEqual(self.web.get('/api/v1/decisions').status_code,200)
        self.assertEqual(self.repo.get(user['_id'],saved['id'])['revision'],1)
        self.assertEqual(self.lifecycle.users.find_one({'_id':user['_id']})['state'],'active')
    def test_boundary_purge_removes_only_owned_records_and_keeps_suppression_marker(self):
        saved=self.create();user=self.user();other=self.user('b')
        self.repo.create(other['_id'],uuid4(),saved['state'])
        requested=self.lifecycle.request(user,uuid4(),clock=1000)
        deadline=requested['delete_after']
        self.assertEqual(self.lifecycle.purge_due(lambda subject:None,clock=deadline-1)['completed'],0)
        with self.assertRaises(StorageError):self.lifecycle.restore(self.lifecycle.users.find_one({'_id':user['_id']}),clock=deadline)
        calls=[];self.assertEqual(self.lifecycle.purge_due(calls.append,clock=deadline)['completed'],1)
        self.assertEqual(calls,['auth0|a']);self.assertEqual(self.repo.decisions.count_documents({'owner_id':user['_id']}),0)
        self.assertEqual(self.repo.decisions.count_documents({'owner_id':other['_id']}),1)
        marker=self.lifecycle.users.find_one({'_id':user['_id']})
        self.assertEqual(marker['state'],'deleted');self.assertNotIn('email',marker);self.assertNotIn('subject',marker)
        ledger=self.lifecycle.ledger.find_one({'_id':'account:'+user['_id']})
        self.assertEqual(ledger['backup_removal_due'],deadline+RECOVERY_SECONDS)
        with self.assertRaises(StorageError):self.store.create_session(self.source.config.issuer,'auth0|a','a@example.com',True,time.time())
        self.assertNotIn('email',self.lifecycle.users.find_one({'_id':user['_id']}))
    def test_provider_failure_retries_without_restoration_or_moving_backup_deadline(self):
        user=self.user();self.lifecycle.request(user,uuid4(),clock=0)
        def fail(subject):raise RuntimeError('provider unavailable')
        result=self.lifecycle.purge_due(fail,clock=RECOVERY_SECONDS)
        self.assertEqual(result['retry_pending'],1)
        record=self.lifecycle.users.find_one({'_id':user['_id']})
        self.assertEqual(record['state'],'purging');self.assertNotIn('email',record)
        with self.assertRaises(StorageError):self.lifecycle.restore(record,clock=RECOVERY_SECONDS)
        self.lifecycle.purge_due(lambda subject:None,clock=RECOVERY_SECONDS+61)
        self.assertEqual(self.lifecycle.ledger.find_one({'_id':'account:'+user['_id']})['backup_removal_due'],2*RECOVERY_SECONDS)
    def test_notifications_retry_and_restore_cancels_unsent_mail(self):
        from backend.app.notifications import deliver_pending
        user=self.user();self.lifecycle.request(user,uuid4(),clock=1000)
        def fail(*args):raise RuntimeError('SMTP unavailable')
        self.assertEqual(deliver_pending(self.repo.database,fail,clock=1000)['retry_pending'],1)
        calls=[];self.assertEqual(deliver_pending(self.repo.database,lambda *args:calls.append(args),clock=1001)['sent'],0)
        self.assertEqual(deliver_pending(self.repo.database,lambda *args:calls.append(args),clock=1200)['sent'],1)
        self.assertEqual(len(calls),1)
        record=self.lifecycle.users.find_one({'_id':user['_id']});self.lifecycle.restore(record,clock=1300)
        self.assertEqual(deliver_pending(self.repo.database,lambda *args:calls.append(args),clock=1400)['sent'],0)
    def test_restore_and_purge_claim_have_only_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        user=self.user();self.lifecycle.request(user,uuid4(),clock=0)
        pending=self.lifecycle.users.find_one({'_id':user['_id']})
        def restore():
            try:self.lifecycle.restore(pending,clock=RECOVERY_SECONDS-1);return True
            except StorageError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            restored=pool.submit(restore)
            purged=pool.submit(lambda:self.lifecycle.purge_due(lambda subject:None,clock=RECOVERY_SECONDS))
            won_restore=restored.result();count=purged.result()['completed']
        self.assertEqual(int(won_restore)+count,1)
        self.assertEqual(self.lifecycle.users.find_one({'_id':user['_id']})['state'],'active' if won_restore else 'deleted')

    def test_workspace_delete_is_revision_checked_private_and_prevents_resurrection(self):
        saved=self.create();key=saved['id'];owner=self.user()['_id']
        from backend.app.workspaces import build_snapshot
        snap=self.repo.save_snapshot(owner,build_snapshot(saved,uuid4()))
        path='/api/v1/decisions/'+key
        self.assertEqual(self.web.request('DELETE',path,headers=self.authenticate('b'),json={'expected_revision':1,'confirmation':'DELETE'}).status_code,404)
        self.assertEqual(self.web.request('DELETE',path,headers=self.authenticate(),json={'expected_revision':2,'confirmation':'DELETE'}).status_code,409)
        result=self.web.request('DELETE',path,headers=self.authenticate(),json={'expected_revision':1,'confirmation':'DELETE'})
        self.assertEqual(result.status_code,204,result.text)
        self.assertEqual(self.web.get(path).status_code,404)
        self.assertEqual(self.web.get(path+'/snapshots/'+snap['id']).status_code,404)
        self.assertEqual(self.repo.list(owner,0,20),[])
        self.assertEqual(self.repo.snapshots.count_documents({'owner_id':owner,'decision_id':key}),0)
        with self.assertRaises(StorageError):self.repo.create(owner,UUID(key),saved['state'])
        with self.assertRaises(StorageError):self.repo.update(owner,key,1,saved['state'])
        self.assertEqual(self.web.request('DELETE',path,headers=self.authenticate(),json={'expected_revision':1,'confirmation':'DELETE'}).status_code,204)
        # Simulate a late child write after a process dies; durable cleanup removes it.
        self.repo.snapshots.insert_one({'_id':'late','owner_id':owner,'decision_id':key})
        self.repo.cleanup_deleted_workspaces()
        self.assertEqual(self.repo.snapshots.count_documents({'owner_id':owner,'decision_id':key}),0)

class ProviderDeletionTests(unittest.TestCase):
    def test_dedicated_scope_encoded_subject_and_retries_are_bounded(self):
        import httpx
        from backend.app import deletion_provider
        from backend.app.auth_provider import AuthSettings
        for delete_status in (204,404,200,503):
            requests=[]
            def handle(request):
                requests.append(request)
                return httpx.Response(200,json={'access_token':'server-only-token'}) if request.url.path=='/oauth/token' else httpx.Response(delete_status)
            client=httpx.Client(transport=httpx.MockTransport(handle))
            with patch.dict(os.environ,{'PDW_AUTH0_DELETION_CLIENT_ID':'deletion-only','PDW_AUTH0_DELETION_CLIENT_SECRET':'private'}), \
                 patch.object(deletion_provider,'settings',return_value=AuthSettings('example.auth0.com','app','secret','read-client','read-secret')), \
                 patch.object(deletion_provider.httpx,'Client',return_value=client):
                if delete_status in (204,404):deletion_provider.delete_identity('auth0|fake')
                else:
                    with self.assertRaises(Exception):deletion_provider.delete_identity('auth0|fake')
            self.assertEqual(len(requests),2)
            self.assertEqual(requests[0].read().decode().count('delete:users'),1)
            self.assertIn('auth0%7Cfake',str(requests[1].url))
            self.assertNotIn('server-only-token',str(requests[1].url))


class MaintenanceOutputTests(unittest.TestCase):
    def test_command_redacts_failures_and_signals_retry(self):
        import io
        from contextlib import redirect_stdout
        from backend.app import maintenance
        output=io.StringIO()
        with patch('sys.argv',['maintenance','--run-once']),patch.object(maintenance,'configured_repository',side_effect=RuntimeError('secret-uri')),redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:maintenance.main()
        self.assertEqual(raised.exception.code,1);self.assertNotIn('secret-uri',output.getvalue())
