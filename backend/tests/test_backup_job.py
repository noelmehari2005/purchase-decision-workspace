"""Daily job idempotency, secret exclusion, key expiry and signed route isolation."""
import hashlib
import hmac
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock,patch

from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from backend.app import backup_job as job,backup_api as api,maintenance_api
from backend.app.workspaces import StorageError

STAMP=1_795_040_000
ENV={'PDW_BACKUP_ENABLED':'1','PDW_BACKUP_ENCRYPTION_KEY':'ab'*32,'PDW_BACKUP_MONGO_PASSWORD':'private-password',
     'PDW_BACKUP_WRITER_KEY_ID':'private-key-id','PDW_BACKUP_WRITER_APPLICATION_KEY':'private-key'}


class JobTests(unittest.TestCase):
    def setUp(self):
        self.db=MagicMock();self.lease=MagicMock();self.lease.acquire.return_value=True
        self.factory=MagicMock(return_value=self.lease);self.capture=MagicMock(return_value=b'encrypted')
        self.upload=MagicMock(return_value={'file_name':'archives/fixture.pdwbackup','sha256':'a'*64,'bytes':8,
                                          'key_expires_at':(STAMP+90*86400)*1000})

    def run_job(self,env=None):
        return job.run_daily(self.db,environ=ENV if env is None else env,clock=lambda:STAMP,
                             capture=self.capture,upload=self.upload,lease_factory=self.factory)

    def test_disabled_and_bad_config_have_no_storage_or_network_work(self):
        self.assertEqual(self.run_job({})['status'],'disabled')
        with self.assertRaises(StorageError):self.run_job({'PDW_BACKUP_ENABLED':'1'})
        self.factory.assert_not_called();self.capture.assert_not_called();self.upload.assert_not_called()

    def test_one_attempt_is_claimed_before_upload_and_safe_metadata_is_saved(self):
        result=self.run_job();self.assertEqual(result,{'status':'ok','mode':'backup','uploaded':True,'writer_rotation_due':False})
        self.factory.assert_called_once_with(self.db,name='backup');self.lease.release.assert_called_once()
        saved=json.dumps(self.db.system_status.mock_calls,default=str)
        for secret in ENV.values():
            if secret.startswith('private'):self.assertNotIn(secret,saved)
        self.assertTrue(self.db.system_status.insert_one.call_args.args[0]['_id'].startswith('backup_run_'))

    def test_busy_and_already_attempted_never_capture_or_upload(self):
        self.lease.acquire.return_value=False
        self.assertEqual(self.run_job()['status'],'busy')
        self.lease.acquire.return_value=True;self.db.system_status.insert_one.side_effect=DuplicateKeyError('duplicate')
        self.assertEqual(self.run_job()['status'],'already_attempted')
        self.capture.assert_not_called();self.upload.assert_not_called()

    def test_capture_or_ambiguous_upload_failure_is_not_retried_and_releases_lease(self):
        for phase in ('capture','upload'):
            self.setUp();getattr(self,phase).side_effect=RuntimeError('PRIVATE URI and key')
            with self.subTest(phase=phase),self.assertRaises(StorageError) as raised:self.run_job()
            self.assertNotIn('PRIVATE',raised.exception.message)
            self.assertEqual(self.db.system_status.update_one.call_args.args[1]['$set']['phase'],phase)
            self.lease.release.assert_called_once()
            if phase=='capture':self.upload.assert_not_called()
            else:self.upload.assert_called_once()

    def test_unknown_or_near_key_expiry_withholds_healthy_result_after_upload(self):
        for expires in (None,(STAMP+13*86400)*1000,float('nan')):
            self.upload.return_value['key_expires_at']=expires
            with self.subTest(expires=expires):
                result=self.run_job();self.assertEqual(result['status'],'attention');self.assertTrue(result['uploaded'])


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{**ENV,'PDW_BACKUP_SIGNING_SECRET':'d'*64,'PDW_MAINTENANCE_ENABLED':'1','PDW_MAINTENANCE_SECRET':'a'*64,
                                       'PDW_MAINTENANCE_MODE':'check'})
        self.env.start();self.addCleanup(self.env.stop)
        self.hosted=patch.object(maintenance_api,'runtime',return_value=SimpleNamespace(hosted=True));self.hosted.start();self.addCleanup(self.hosted.stop)
        self.clock=patch.object(maintenance_api.time,'time',return_value=STAMP);self.clock.start();self.addCleanup(self.clock.stop)
        self.repo=patch.object(api,'configured_repository');self.repository=self.repo.start();self.addCleanup(self.repo.stop)
        self.work=patch.object(api,'run_daily',return_value={'status':'ok','mode':'backup','uploaded':True})
        self.run=self.work.start();self.addCleanup(self.work.stop)
        app=FastAPI();app.include_router(api.router)
        @app.exception_handler(StorageError)
        async def denied(_request:Request,error:StorageError):return JSONResponse(status_code=error.status,content={'code':error.code})
        self.client=TestClient(app)

    def headers(self,path=api.PATH):
        nonce='b'*32;message=f'POST\n{path}\n{STAMP}\n{nonce}'
        return {'X-PDW-Timestamp':str(STAMP),'X-PDW-Nonce':nonce,
                'X-PDW-Signature':hmac.new(('d'*64).encode(),message.encode(),hashlib.sha256).hexdigest()}

    def test_unsigned_browser_other_route_and_disabled_calls_fail_before_storage(self):
        for headers in ({},{**self.headers(),'Origin':'https://example.invalid'},self.headers(maintenance_api.PATH)):
            self.assertEqual(self.client.post(api.PATH,headers=headers).status_code,401)
        with patch.dict(os.environ,{'PDW_BACKUP_ENABLED':'0'}):
            self.assertEqual(self.client.post(api.PATH,headers=self.headers()).status_code,404)
        self.repository.assert_not_called();self.run.assert_not_called()

    def test_signed_route_is_replay_guarded_and_does_not_accept_client_mode(self):
        self.repository.return_value.database.maintenance_nonces.insert_one.side_effect=[None,DuplicateKeyError('duplicate')]
        self.assertEqual(self.client.post(api.PATH,headers=self.headers(),json={'mode':'delete'}).status_code,200)
        self.assertEqual(self.client.post(api.PATH,headers=self.headers()).status_code,409)
        self.run.assert_called_once_with(self.repository.return_value.database)

    def test_backup_signing_secret_and_enable_flag_are_independent(self):
        with patch.dict(os.environ,{'PDW_MAINTENANCE_ENABLED':'0','PDW_MAINTENANCE_SECRET':'c'*64,
                                    'PDW_MAINTENANCE_MODE':'not-used-by-backup'}):
            self.assertEqual(self.client.post(api.PATH,headers=self.headers()).status_code,200)

    def test_reused_encryption_or_maintenance_secret_is_rejected_before_storage(self):
        for secret in (ENV['PDW_BACKUP_ENCRYPTION_KEY'],'a'*64):
            with patch.dict(os.environ,{'PDW_BACKUP_SIGNING_SECRET':secret}):
                self.assertEqual(self.client.post(api.PATH,headers=self.headers()).status_code,503)
        self.repository.assert_not_called();self.run.assert_not_called()


@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI for disposable backup job concurrency test.')
class MongoJobTests(unittest.TestCase):
    def test_concurrent_daily_calls_upload_once_and_later_calls_cannot_retry_that_day(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event,Lock
        from uuid import uuid4
        from pymongo import MongoClient
        from backend.app.backup_archive import local_uri
        token=uuid4().hex;name='pdw_backup_job_test_'+token
        started=Event();finish=Event();lock=Lock();uploads=[];owned=False
        with MongoClient(local_uri(os.environ['PDW_TEST_MONGO_URI']),serverSelectionTimeoutMS=3000,timeoutMS=10000) as client:
            client.admin.command('ping');db=client[name]
            try:
                if db.list_collection_names():self.fail('Random fixture namespace was already occupied.')
                db.fixture_manifest.insert_one({'_id':token});owned=True
                def capture(_password,_key):
                    started.set()
                    if not finish.wait(5):raise RuntimeError('fixture timeout')
                    return b'fictional encrypted fixture'
                def upload(*_args):
                    with lock:uploads.append('one')
                    return {'file_name':'archives/fixture.pdwbackup','sha256':'a'*64,'bytes':27,
                            'key_expires_at':(STAMP+90*86400)*1000}
                def run():return job.run_daily(db,environ=ENV,clock=lambda:STAMP,capture=capture,upload=upload)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first=pool.submit(run)
                    try:
                        self.assertTrue(started.wait(5))
                        second=pool.submit(run).result(timeout=5)
                        self.assertEqual(second['status'],'busy')
                    finally:finish.set()
                    self.assertEqual(first.result(timeout=5)['status'],'ok')
                self.assertEqual(run()['status'],'already_attempted');self.assertEqual(uploads,['one'])
                self.assertEqual(db.system_status.count_documents({}),1)
                self.assertEqual(db.maintenance_locks.find_one({'_id':'backup'})['lease_until'],0)
            finally:
                finish.set()
                if owned and db.fixture_manifest.find_one({'_id':token}):client.drop_database(name)
