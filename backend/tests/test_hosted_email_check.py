import os
import smtplib
import unittest
from unittest.mock import MagicMock,patch
from pymongo.errors import DuplicateKeyError
from backend.app import hosted_email_check as probe,maintenance
from backend.app.workspaces import StorageError


class HostedEmailCheckTests(unittest.TestCase):
    def setUp(self):
        env=patch.dict(os.environ,{'PDW_EMAIL_TEST_TO':'fixture@example.com','PDW_EMAIL_TEST_ID':'a'*32})
        env.start();self.addCleanup(env.stop)
        self.db=MagicMock()

    def test_exactly_one_attempt_for_same_id_without_user_or_notice_operations(self):
        self.db.system_status.insert_one.side_effect=[None,DuplicateKeyError('already used')]
        with patch.object(probe,'send_test_message') as send:
            self.assertEqual(probe.run(self.db)['delivery'],'accepted')
            self.assertEqual(probe.run(self.db)['delivery'],'already_attempted')
            send.assert_called_once_with('fixture@example.com')
        self.assertEqual(set(self.db._mock_children),{'system_status'})
        for call in self.db.system_status.method_calls:
            self.assertNotIn('fixture@example.com',str(call))

    def test_failed_or_ambiguous_send_is_not_automatically_retried_and_is_redacted(self):
        self.db.system_status.insert_one.side_effect=[None,DuplicateKeyError('already used')]
        with patch.object(probe,'send_test_message',side_effect=smtplib.SMTPAuthenticationError(535,b'PRIVATE key person@example.com')) as send:
            with self.assertLogs('pdw.email_test',level='WARNING') as logs:
                with self.assertRaises(StorageError):probe.run(self.db)
            self.assertEqual(probe.run(self.db)['delivery'],'already_attempted')
            send.assert_called_once()
        self.assertIn('authentication',str(logs.output))
        self.assertNotIn('PRIVATE',str(logs.output)+str(self.db.system_status.method_calls))

    def test_missing_invalid_or_multiple_recipients_never_claim_or_send(self):
        for config in ({'PDW_EMAIL_TEST_TO':''},{'PDW_EMAIL_TEST_TO':'a@example.com,b@example.com'},
                       {'PDW_EMAIL_TEST_TO':'a@example.com\r\nBcc: b@example.com'}, {'PDW_EMAIL_TEST_ID':'bad'}):
            with patch.dict(os.environ,config),patch.object(probe,'send_test_message') as send:
                with self.assertRaises(StorageError):probe.run(self.db)
                send.assert_not_called()
        self.db.system_status.insert_one.assert_not_called()

    def test_probe_mode_cannot_process_notices_accounts_or_workspaces(self):
        self.db.maintenance_locks.update_one.return_value.matched_count=1
        with patch.object(probe,'run',return_value={'status':'ok','mode':'email-test','delivery':'accepted'}), \
             patch.object(maintenance,'deliver_pending') as notices,patch.object(maintenance,'AccountLifecycle') as lifecycle, \
             patch('backend.app.repositories.MongoRepository') as repo:
            self.assertEqual(maintenance.run(self.db,mode='email-test')['delivery'],'accepted')
        notices.assert_not_called();lifecycle.assert_not_called();repo.assert_not_called()
        for call in self.db.system_status.update_one.call_args_list:
            self.assertEqual(call.args[0]['_id'],'maintenance_email-test')
