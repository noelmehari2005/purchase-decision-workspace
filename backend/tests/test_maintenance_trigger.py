"""Signed scheduler, replay/lease fencing and bounded work; no real services."""
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

from backend.app import maintenance_api as api,maintenance
from backend.app.maintenance_lease import MaintenanceLease,LeaseLost
from backend.app.workspaces import StorageError

SECRET='a'*64
STAMP=1795040000


def signed_headers(stamp=STAMP,nonce='b'*32,secret=SECRET):
    message=f'POST\n{api.PATH}\n{stamp}\n{nonce}'
    return {'X-PDW-Timestamp':str(stamp),'X-PDW-Nonce':nonce,
            'X-PDW-Signature':hmac.new(secret.encode(),message.encode(),hashlib.sha256).hexdigest()}


class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'PDW_MAINTENANCE_ENABLED':'1','PDW_MAINTENANCE_SECRET':SECRET,
                                      'PDW_MAINTENANCE_MODE':'check'})
        self.env.start();self.addCleanup(self.env.stop)
        self.hosted=patch.object(api,'runtime',return_value=SimpleNamespace(hosted=True))
        self.hosted.start();self.addCleanup(self.hosted.stop)
        self.clock=patch.object(api.time,'time',return_value=STAMP)
        self.clock.start();self.addCleanup(self.clock.stop)
        app=FastAPI();app.include_router(api.router)
        @app.exception_handler(StorageError)
        async def denied(_request:Request,error:StorageError):
            return JSONResponse(status_code=error.status,content={'code':error.code,'message':error.message})
        self.client=TestClient(app)
        self.repo=patch.object(api,'configured_repository');self.repository=self.repo.start();self.addCleanup(self.repo.stop)
        self.work=patch.object(api,'run',return_value={'status':'ok','mode':'check'})
        self.run=self.work.start();self.addCleanup(self.work.stop)

    def test_disabled_and_local_modes_have_no_database_side_effects(self):
        for env,hosted in [({'PDW_MAINTENANCE_ENABLED':'0'},True),({},False)]:
            with patch.dict(os.environ,env),patch.object(api,'runtime',return_value=SimpleNamespace(hosted=hosted)):
                self.assertEqual(self.client.post(api.PATH,headers=signed_headers()).status_code,404)
        self.repository.assert_not_called();self.run.assert_not_called()

    def test_unsigned_browser_stale_future_and_tampered_calls_are_rejected_before_storage(self):
        cases=[{}, {'Authorization':'Bearer ordinary-user-session'},
               {**signed_headers(),'Origin':'https://owner.github.io'},
               signed_headers(stamp=STAMP-121),signed_headers(stamp=STAMP+121),
               signed_headers(secret='c'*64),{**signed_headers(),'X-PDW-Nonce':'bad'},
               {**signed_headers(),'X-PDW-Timestamp':'not-a-time'}]
        for headers in cases:
            with self.subTest(headers=list(headers)):
                self.assertEqual(self.client.post(api.PATH,headers=headers).status_code,401)
        self.assertEqual(self.client.post(api.PATH+'?token=not-a-secret',headers=signed_headers()).status_code,401)
        self.repository.assert_not_called();self.run.assert_not_called()

    def test_configuration_failures_do_not_expose_secret(self):
        for patch_env in ({'PDW_MAINTENANCE_SECRET':'PRIVATE-invalid'}, {'PDW_MAINTENANCE_MODE':'purge-everything'}):
            with patch.dict(os.environ,patch_env):
                result=self.client.post(api.PATH,headers=signed_headers())
                self.assertEqual(result.status_code,503)
                self.assertNotIn('PRIVATE',result.text)
        self.repository.assert_not_called()

    def test_valid_request_is_bounded_and_server_mode_cannot_be_overridden(self):
        result=self.client.post(api.PATH,headers={**signed_headers(),'X-PDW-Mode':'cleanup'},json={'mode':'cleanup'})
        self.assertEqual(result.status_code,200,result.text)
        self.run.assert_called_once_with(self.repository.return_value.database,mode='check',limit=1,budget_seconds=35)
        row=self.repository.return_value.database.maintenance_nonces.insert_one.call_args.args[0]
        self.assertNotIn(SECRET,json.dumps(row,default=str))
        self.assertNotIn('b'*32,json.dumps(row,default=str))
        self.assertGreater(row['expires_at'].timestamp(),STAMP+2*api.WINDOW_SECONDS)

    def test_replay_is_rejected_without_running_work_twice(self):
        db=self.repository.return_value.database
        db.maintenance_nonces.insert_one.side_effect=[None,DuplicateKeyError('duplicate nonce')]
        first=self.client.post(api.PATH,headers=signed_headers())
        second=self.client.post(api.PATH,headers=signed_headers())
        self.assertEqual(first.status_code,200);self.assertEqual(second.status_code,409)
        self.assertEqual(second.json()['code'],'maintenance_replay');self.run.assert_called_once()

    def test_failure_response_and_logs_exclude_private_details(self):
        self.run.side_effect=RuntimeError('SECRET database-uri person@example.com')
        with self.assertLogs('pdw.maintenance',level='WARNING') as logs:
            result=self.client.post(api.PATH,headers=signed_headers())
        self.assertEqual(result.status_code,503)
        for private in ('SECRET','database-uri','person@example.com',SECRET):
            self.assertNotIn(private,result.text+' '.join(logs.output))
        self.assertNotIn(api.PATH,self.client.get('/openapi.json').json()['paths'])


class LeaseTests(unittest.TestCase):
    def test_busy_unique_lease_is_not_overwritten(self):
        db=MagicMock();db.maintenance_locks.find_one_and_update.side_effect=DuplicateKeyError('busy')
        lease=MaintenanceLease(db)
        self.assertFalse(lease.acquire())
        query,update=db.maintenance_locks.find_one_and_update.call_args.args
        self.assertEqual(query['_id'],'maintenance');self.assertIn('$or',query)
        self.assertEqual(update['$set']['owner'],lease.owner)
        db.system_status.update_one.assert_not_called()

    def test_expired_or_replaced_owner_cannot_renew_or_release_a_different_owner(self):
        db=MagicMock();lease=MaintenanceLease(db)
        db.maintenance_locks.update_one.return_value.matched_count=0
        with self.assertRaises(LeaseLost):lease.renew()
        lease.release()
        for call in db.maintenance_locks.update_one.call_args_list:
            self.assertEqual(call.args[0]['owner'],lease.owner)
        self.assertIn('lease_until',db.maintenance_locks.update_one.call_args_list[0].args[0])


class WorkerBoundsTests(unittest.TestCase):
    def database(self):
        db=MagicMock();db.maintenance_locks.update_one.return_value.matched_count=1
        return db

    def test_check_only_reports_without_email_purge_or_a_full_cleanup_heartbeat(self):
        db=self.database()
        with patch.object(maintenance,'deliver_pending') as send,patch.object(maintenance,'AccountLifecycle') as lifecycle, \
             patch('backend.app.repositories.MongoRepository') as repo, \
             patch('backend.app.readiness.configuration_report',return_value={'checks':[]}), \
             patch('backend.app.readiness.database_report',return_value={'maintenance':'not_observed'}):
            result=maintenance.run(db,mode='check',limit=1)
        self.assertEqual(result['mode'],'check')
        send.assert_not_called();lifecycle.assert_not_called();repo.assert_not_called()
        for call in db.system_status.update_one.call_args_list:
            self.assertEqual(call.args[0]['_id'],'maintenance_check')
        self.assertEqual(db.maintenance_locks.update_one.call_args.args[1]['$set']['lease_until'],0)

    def test_busy_run_does_not_touch_status_or_dependencies(self):
        db=self.database();db.maintenance_locks.find_one_and_update.side_effect=DuplicateKeyError('busy')
        with patch.object(maintenance,'deliver_pending') as send:
            self.assertEqual(maintenance.run(db),{'status':'busy','mode':'cleanup'})
        send.assert_not_called();db.system_status.update_one.assert_not_called()

    def test_notify_mode_cannot_purge_accounts_or_workspaces(self):
        db=self.database()
        with patch.object(maintenance,'deliver_pending',return_value={'sent':1,'retry_pending':0}), \
             patch.object(maintenance,'AccountLifecycle') as lifecycle,patch('backend.app.repositories.MongoRepository') as repo:
            result=maintenance.run(db,mode='notify',limit=1)
        self.assertEqual(result['status'],'ok');self.assertEqual(result['accounts']['completed'],0)
        lifecycle.assert_not_called();repo.return_value.cleanup_deleted_workspaces.assert_not_called()

    def test_deadline_stops_new_claims_without_changing_existing_deletion_deadlines(self):
        from backend.app.notifications import deliver_pending
        from backend.app.lifecycle import AccountLifecycle
        from backend.app.repositories import MongoRepository
        db=self.database()
        self.assertEqual(deliver_pending(db,should_continue=lambda:False),{'sent':0,'retry_pending':0})
        db.users.find_one_and_update.assert_not_called()
        db.users.find.return_value.limit.return_value.max_time_ms.return_value=[{'_id':'fixture'}]
        self.assertEqual(AccountLifecycle(db).purge_due(MagicMock(),should_continue=lambda:False),{'completed':0,'retry_pending':0})
        db.users.find_one_and_update.assert_not_called()
        db.decisions.find.return_value.sort.return_value.limit.return_value.max_time_ms.return_value=[{'_id':'fixture'}]
        self.assertEqual(MongoRepository(db).cleanup_deleted_workspaces(should_continue=lambda:False),0)
        db.snapshots.delete_many.assert_not_called()

    def test_failures_release_the_global_lease_and_record_only_safe_status(self):
        db=self.database()
        with patch.object(maintenance,'deliver_pending',side_effect=RuntimeError('private-provider-response')):
            with self.assertRaises(RuntimeError):maintenance.run(db)
        last=db.system_status.update_one.call_args.args[1]['$set']
        self.assertEqual(last['status'],'failed');self.assertNotIn('private',json.dumps(last))
        self.assertEqual(db.maintenance_locks.update_one.call_args.args[1]['$set']['lease_until'],0)


@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI for disposable scheduler integration tests.')
class MongoSchedulerTests(unittest.TestCase):
    def setUp(self):
        from pymongo import MongoClient
        from uuid import uuid4
        self.client=MongoClient(os.environ['PDW_TEST_MONGO_URI'],serverSelectionTimeoutMS=2000,tz_aware=True)
        self.db=self.client['pdw_test_'+uuid4().hex]

    def tearDown(self):
        self.client.drop_database(self.db.name);self.client.close()

    def test_concurrent_claims_have_one_winner_and_old_release_cannot_unlock_successor(self):
        from concurrent.futures import ThreadPoolExecutor
        import time
        leases=[MaintenanceLease(self.db) for _ in range(12)]
        # Precreate the collection so first-use implicit collection creation is
        # not conflated with the unique-lease race being tested.
        self.db.maintenance_locks.insert_one({'_id':'maintenance','lease_until':0})
        with ThreadPoolExecutor(max_workers=12) as pool:
            acquired=list(pool.map(lambda lease:lease.acquire(),leases))
        self.assertEqual(sum(acquired),1)
        old=leases[acquired.index(True)]
        successor=MaintenanceLease(self.db)
        with patch('backend.app.maintenance_lease.time.time',return_value=time.time()+181):
            self.assertTrue(successor.acquire())
            old.release()
            self.assertEqual(self.db.maintenance_locks.find_one({'_id':'maintenance'})['owner'],successor.owner)
            with self.assertRaises(LeaseLost):old.renew()
            successor.renew();successor.release()

    def test_database_replay_guard_accepts_a_signature_only_once(self):
        import time
        app=FastAPI();app.include_router(api.router)
        @app.exception_handler(StorageError)
        async def denied(_request:Request,error:StorageError):
            return JSONResponse(status_code=error.status,content={'code':error.code})
        with patch.dict(os.environ,{'PDW_MAINTENANCE_ENABLED':'1','PDW_MAINTENANCE_SECRET':SECRET,'PDW_MAINTENANCE_MODE':'check'}), \
             patch.object(api,'runtime',return_value=SimpleNamespace(hosted=True)), \
             patch.object(api,'configured_repository',return_value=SimpleNamespace(database=self.db)), \
             patch.object(api,'run',return_value={'status':'ok','mode':'check'}) as work:
            client=TestClient(app);headers=signed_headers(stamp=int(time.time()))
            self.assertEqual(client.post(api.PATH,headers=headers).status_code,200)
            self.assertEqual(client.post(api.PATH,headers=headers).status_code,409)
            work.assert_called_once()
