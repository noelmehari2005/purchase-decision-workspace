"""Real backup entry-point guards; no external connections or real credentials."""
import io
from urllib.parse import urlsplit, unquote
import unittest
from unittest.mock import MagicMock, patch

from backend.app import backup_staging as staging
from backend.app.backup_archive import BackupError


class StagingBackupTests(unittest.TestCase):
    def setUp(self):
        self.factory=MagicMock();self.client=self.factory.return_value.__enter__.return_value
        self.auth={'authenticatedUsers':[{'user':staging.USER,'db':'admin'}],
                   'authenticatedUserRoles':[{'role':'read','db':staging.DATABASE}]}
        self.client.admin.command.return_value={'authInfo':self.auth}
        self.capture=MagicMock(return_value=b'encrypted archive')

    def test_fixed_target_verified_read_role_and_password_encoded_once(self):
        password='contains:@/?#%+ space'
        result=staging.capture_staging(password,b'k'*32,client_factory=self.factory,capture=self.capture)
        self.assertEqual(result,b'encrypted archive')
        uri=self.factory.call_args.args[0];options=self.factory.call_args.kwargs
        self.assertEqual(urlsplit(uri).hostname,staging.HOST)
        self.assertEqual(unquote(urlsplit(uri).password),password)
        self.assertTrue(options['tls']);self.assertTrue(options['tlsCAFile'])
        self.capture.assert_called_once_with(self.client[staging.DATABASE],b'k'*32,staging.SOURCE)

    def test_app_write_role_admin_wrong_database_or_principal_never_capture(self):
        for field,value in [('authenticatedUserRoles',[{'role':'readWrite','db':staging.DATABASE}]),
                            ('authenticatedUserRoles',[{'role':'readAnyDatabase','db':'admin'}]),
                            ('authenticatedUserRoles',[{'role':'read','db':'other'}]),
                            ('authenticatedUsers',[{'user':'pdw_staging_app','db':'admin'}])]:
            before=self.auth[field];self.auth[field]=value
            with self.subTest(value=value),self.assertRaises(BackupError):
                staging.capture_staging('password',b'k'*32,client_factory=self.factory,capture=self.capture)
            self.auth[field]=before
        self.capture.assert_not_called()

    def test_malformed_key_or_password_never_connects(self):
        for value in ('short','g'*64,' '*64,'a'*63,'a'*65):
            with self.subTest(value=value),self.assertRaises(BackupError):staging.encryption_key(value)
        self.assertEqual(staging.encryption_key('AB'*32),bytes.fromhex('ab'*32))
        with self.assertRaises(BackupError):staging.capture_staging('',b'k'*32,client_factory=self.factory)
        self.factory.assert_not_called()

    def test_connection_failures_hide_private_uri_and_details(self):
        self.factory.side_effect=RuntimeError('PRIVATE credential URI')
        with self.assertRaises(BackupError) as raised:staging.capture_staging('password',b'k'*32,client_factory=self.factory)
        self.assertNotIn('PRIVATE',str(raised.exception));self.capture.assert_not_called()

    def test_cli_capture_failure_never_uploads_and_redacts_secrets(self):
        output=io.StringIO()
        with patch('sys.argv',['backup','--capture-and-upload']),patch('sys.stdin.isatty',return_value=True),\
                patch('builtins.input',return_value='BACK UP STAGING'),\
                patch('getpass.getpass',side_effect=['ab'*32,'private-password','private-id','private-appkey']),\
                patch.object(staging,'capture_staging',side_effect=BackupError('PRIVATE server data')),\
                patch.object(staging,'upload_archive') as upload,patch('sys.stdout',output):
            self.assertEqual(staging.main(),1)
        upload.assert_not_called();self.assertNotIn('PRIVATE',output.getvalue())
        self.assertNotIn('private-password',output.getvalue());self.assertIn('database-capture',output.getvalue())

    def test_cli_cancel_or_noninteractive_never_requests_credentials(self):
        for interactive in (True,False):
            with patch('sys.argv',['backup','--capture-and-upload']),patch('sys.stdin.isatty',return_value=interactive),\
                    patch('builtins.input',return_value='no'),patch('getpass.getpass') as secret,patch('sys.stdout',io.StringIO()):
                self.assertEqual(staging.main(),1)
            secret.assert_not_called()

    def test_capture_check_uses_two_hidden_prompts_and_never_uploads(self):
        from backend.app.backup_archive import seal, COLLECTIONS
        blob=seal({n:[] for n in COLLECTIONS},bytes.fromhex('ab'*32),staging.SOURCE)
        output=io.StringIO()
        with patch('sys.argv',['backup','--check-capture']),patch('sys.stdin.isatty',return_value=True),\
                patch('builtins.input',return_value='CHECK STAGING CAPTURE'),\
                patch('getpass.getpass',side_effect=['ab'*32,'private-password']) as secret,\
                patch.object(staging,'capture_staging',return_value=blob),\
                patch.object(staging,'upload_archive') as upload,patch('sys.stdout',output):
            self.assertEqual(staging.main(),0)
        upload.assert_not_called();self.assertEqual(secret.call_count,2)
        self.assertIn('"uploaded": false',output.getvalue());self.assertNotIn('private-password',output.getvalue())
