"""Operator diagnostics are redacted and read-only; heartbeats describe real work."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock,patch
from backend.app.readiness import configuration_report,database_report

class ReadinessTests(unittest.TestCase):
    def env(self):
        return {'PDW_LOCAL_STORAGE':'1','PDW_AUTH_MODE':'auth0','PDW_AUTH0_DOMAIN':'example.auth0.com',
            'PDW_AUTH0_CLIENT_ID':'app','PDW_AUTH0_CLIENT_SECRET':'SECRET-A',
            'PDW_AUTH0_MANAGEMENT_CLIENT_ID':'read-client','PDW_AUTH0_MANAGEMENT_CLIENT_SECRET':'SECRET-B',
            'PDW_ICECAT_API_TOKEN':'SECRET-C','PDW_SMTP_HOST':'smtp.example.com','PDW_SMTP_FROM':'app@example.com',
            'PDW_SMTP_USERNAME':'private-user','PDW_SMTP_PASSWORD':'SECRET-D',
            'PDW_AUTH0_DELETION_CLIENT_ID':'deletion-client','PDW_AUTH0_DELETION_CLIENT_SECRET':'SECRET-E'}
    def test_configured_is_not_verified_or_public_release_ready(self):
        env=self.env();report=configuration_report(env)
        self.assertTrue(all(c['status']=='configured_unverified' for c in report['checks']))
        self.assertFalse(report['release_ready'])
        raw=json.dumps(report)
        for private in ['SECRET-','app@example.com','smtp.example.com','private-user','read-client']:
            self.assertNotIn(private,raw)
    def test_missing_invalid_and_reused_privileged_client_are_visible(self):
        self.assertTrue(all(c['status']=='missing' for c in configuration_report({})['checks']))
        for key,value,check in [('PDW_SMTP_PORT','not-a-number','notification_smtp'),
                                ('PDW_SMTP_FROM','invalid','notification_smtp'),
                                ('PDW_AUTH0_DOMAIN','evil.test','email_password_auth'),
                                ('PDW_AUTH0_DELETION_CLIENT_ID','read-client','dedicated_auth0_cleanup')]:
            env=self.env();env[key]=value
            self.assertEqual(next(c for c in configuration_report(env)['checks'] if c['check']==check)['status'],'invalid')
    def database(self,record):
        db=MagicMock();db.system_status.find_one.return_value=record
        db.users.count_documents.return_value=0;db.deletion_ledger.count_documents.return_value=0
        return db
    def test_recent_stale_stalled_and_missing_heartbeats(self):
        cases=[({},'not_observed'),({'status':'ok','finished_at':999},'ok'),
               ({'status':'ok','finished_at':800},'stale'),({'status':'running','started_at':999},'running'),
               ({'status':'running','started_at':600},'stalled'),({'status':'failed','finished_at':999},'retry_or_failure')]
        for record,expected in cases:
            with self.subTest(expected=expected):
                db=self.database(record);report=database_report(db,1000)
                self.assertEqual(report['maintenance'],expected)
                db.users.delete_many.assert_not_called();db.system_status.update_one.assert_not_called()
    def test_overdue_work_requires_attention_even_after_successful_worker(self):
        db=self.database({'status':'ok','finished_at':999});db.users.count_documents.return_value=1
        self.assertTrue(database_report(db,1000)['attention_required'])
    def test_connectivity_failure_does_not_echo_uri_or_credentials(self):
        from backend.app import readiness
        output=io.StringIO()
        with patch('sys.argv',['readiness','--check-database']),patch.object(readiness,'inspect_database',side_effect=RuntimeError('mongodb://SECRET')),redirect_stdout(output):
            with self.assertRaises(SystemExit):readiness.main()
        self.assertNotIn('SECRET',output.getvalue());self.assertEqual(json.loads(output.getvalue())['database']['status'],'unavailable')

class HeartbeatTests(unittest.TestCase):
    def test_success_and_failure_have_bounded_safe_heartbeat(self):
        from backend.app import maintenance
        for fail in (False,True):
            db=MagicMock()
            with patch.object(maintenance,'deliver_pending',return_value={'sent':0,'retry_pending':0}), \
                 patch.object(maintenance,'AccountLifecycle') as lifecycle, \
                 patch('backend.app.repositories.MongoRepository') as repository:
                lifecycle.return_value.purge_due.return_value={'completed':0,'retry_pending':0}
                repository.return_value.cleanup_deleted_workspaces.return_value=0
                if fail:repository.return_value.cleanup_deleted_workspaces.side_effect=RuntimeError('secret')
                if fail:
                    with self.assertRaises(RuntimeError):maintenance.run(db)
                else:maintenance.run(db)
            last=db.system_status.update_one.call_args.args[1]['$set']
            self.assertEqual(last['status'],'failed' if fail else 'ok')
            self.assertNotIn('secret',json.dumps(last));self.assertIsInstance(last['finished_at'],float)

import os
from uuid import uuid4

@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI for read-only diagnostics integration.')
class MongoReadinessTests(unittest.TestCase):
    def setUp(self):
        from pymongo import MongoClient
        self.client=MongoClient(os.environ['PDW_TEST_MONGO_URI'],serverSelectionTimeoutMS=2000,tz_aware=True)
        self.name='pdw_test_'+uuid4().hex;self.database=self.client[self.name]
    def tearDown(self):self.client.drop_database(self.name);self.client.close()
    def test_real_heartbeat_and_diagnostics_do_not_run_cleanup(self):
        from backend.app.maintenance import run
        run(self.database,delete_user=lambda subject:None,send=lambda *args:None)
        self.assertEqual(database_report(self.database)['maintenance'],'ok')
        self.database.users.insert_one({'_id':'disposable','state':'pending_deletion','delete_after':1,
                                        'email':'fixture@example.com','delete_requested_at':0,'deletion_notice':{'status':'queued'}})
        before=self.database.users.find_one({'_id':'disposable'})
        report=database_report(self.database)
        self.assertTrue(report['attention_required']);self.assertEqual(report['counts']['accounts_past_recovery_deadline'],1)
        self.assertEqual(self.database.users.find_one({'_id':'disposable'}),before)
