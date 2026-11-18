"""SMTP probe uses synthetic content and never requires lifecycle/database work."""
import io
import os
import smtplib
import socket
import ssl
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from backend.app.email_check import main,delivery_error
from backend.app.notifications import send_message


class EmailCheckTests(unittest.TestCase):
    def test_resend_alternate_tls_port_uses_verified_implicit_tls(self):
        with patch.dict(os.environ,{'PDW_SMTP_HOST':'smtp.resend.com','PDW_SMTP_PORT':'2465','PDW_SMTP_FROM':'app@example.com'}), \
                patch('backend.app.notifications.smtplib.SMTP_SSL') as tls,patch('backend.app.notifications.smtplib.SMTP') as plain:
            tls.return_value.__enter__.return_value.send_message.return_value={}
            send_message('tester@example.com','Test','Synthetic test')
            self.assertTrue(tls.call_args.kwargs['context'].check_hostname)
            plain.assert_not_called()
            tls.return_value.__enter__.return_value.starttls.assert_not_called()

    def test_smtp_has_trusted_roots_and_verification_without_system_ca_paths(self):
        env={'PDW_SMTP_HOST':'smtp.example.com','PDW_SMTP_FROM':'app@example.com','PDW_SMTP_PORT':'465',
             'SSL_CERT_FILE':'/nonexistent/pdw-cafile','SSL_CERT_DIR':'/nonexistent/pdw-cadir'}
        with patch.dict(os.environ,env),patch('backend.app.notifications.smtplib.SMTP_SSL') as smtp:
            smtp.return_value.__enter__.return_value.send_message.return_value={}
            send_message('tester@example.com','Test','Synthetic test')
            context=smtp.call_args.kwargs['context']
            self.assertIs(context.check_hostname,True)
            self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
            self.assertGreater(context.cert_store_stats()['x509_ca'],0)

    def test_diagnostics_distinguish_failures_without_echoing_provider_text(self):
        private=b'private-key tester@example.com'
        cases=[(smtplib.SMTPAuthenticationError(535,private),'authentication (SMTP 535)'),
               (smtplib.SMTPSenderRefused(550,private,'tester@example.com'),'sender (SMTP 550)'),
               (smtplib.SMTPRecipientsRefused({'tester@example.com':(550,private)}),'recipient:'),
               (ssl.SSLCertVerificationError(1,private.decode()),'certificate:'),
               (socket.gaierror(-2,private.decode()),'dns:'),
               (TimeoutError(private.decode()),'timeout:'),
               (smtplib.SMTPDataError(554,private),'server (SMTP 554)'),
               (ConnectionRefusedError(private.decode()),'connection:')]
        for error,expected in cases:
            with self.subTest(expected=expected):
                result=delivery_error(error)
                self.assertTrue(result.startswith(expected))
                self.assertNotIn('private-key',result)
                self.assertNotIn('tester@example.com',result)

    def test_probe_content_is_clearly_a_test_and_failure_output_is_redacted(self):
        with patch('backend.app.email_check.send_message') as send,redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--to','tester@example.com']),0)
            recipient,subject,body=send.call_args.args
            self.assertEqual(recipient,'tester@example.com')
            self.assertIn('delivery test',subject)
            self.assertIn('No account deletion was requested',body)
            self.assertIn('acceptance alone does not prove',output.getvalue())
        with patch('backend.app.email_check.send_message',side_effect=RuntimeError('private-key tester@example.com')),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--to','tester@example.com']),1)
            self.assertNotIn('private-key',output.getvalue())
            self.assertNotIn('tester@example.com',output.getvalue())

    def test_starttls_failure_never_authenticates_or_sends(self):
        env={'PDW_SMTP_HOST':'smtp.example.com','PDW_SMTP_FROM':'app@example.com','PDW_SMTP_PORT':'587',
             'PDW_SMTP_USERNAME':'resend','PDW_SMTP_PASSWORD':'fake-secret'}
        with patch.dict(os.environ,env),patch('backend.app.notifications.smtplib.SMTP') as smtp:
            client=smtp.return_value.__enter__.return_value
            client.starttls.side_effect=RuntimeError('TLS failure')
            with self.assertRaises(RuntimeError):send_message('tester@example.com','Test','Synthetic test')
            client.login.assert_not_called();client.send_message.assert_not_called()

    def test_invalid_recipient_fails_before_opening_connection(self):
        with patch.dict(os.environ,{'PDW_SMTP_HOST':'smtp.example.com','PDW_SMTP_FROM':'app@example.com'}), \
                patch('backend.app.notifications.smtplib.SMTP_SSL') as smtp:
            with self.assertRaises(ValueError):send_message('test@example.com\nBcc:other@example.com','Test','Synthetic test')
            smtp.assert_not_called()
