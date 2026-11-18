"""Explicit SMTP delivery probe. No database access or account lifecycle actions."""
import argparse
import smtplib
import socket
import ssl
from pathlib import Path
from .notifications import send_message


def delivery_error(error):
    # Classify failures without echoing server text, addresses or credentials.
    code=getattr(error,'smtp_code',None)
    status=f' (SMTP {code})' if type(code) is int and 100<=code<=599 else ''
    if isinstance(error,smtplib.SMTPAuthenticationError):
        return 'authentication'+status+': SMTP rejected the login. Check the SMTP username and sending API key.'
    if isinstance(error,smtplib.SMTPSenderRefused):
        return 'sender'+status+': SMTP rejected the From address. Check sender verification and key permissions.'
    if isinstance(error,smtplib.SMTPRecipientsRefused):
        return 'recipient: SMTP rejected the recipient. The Resend testing sender requires your Resend account email.'
    if isinstance(error,ssl.SSLCertVerificationError):
        return 'certificate: TLS certificate verification failed. Check the Python certificate setup; keep verification enabled.'
    if isinstance(error,ssl.SSLError):
        return 'tls: The encrypted connection failed. Check the SMTP port and TLS settings.'
    if isinstance(error,socket.gaierror):
        return 'dns: The SMTP hostname could not be resolved. Check the hostname and network connection.'
    if isinstance(error,TimeoutError):
        return 'timeout: The SMTP server did not respond in time. Check network access to the configured port.'
    if isinstance(error,smtplib.SMTPResponseException):
        return 'server'+status+': SMTP refused the request. Check provider delivery logs and account restrictions.'
    if isinstance(error,smtplib.SMTPNotSupportedError):
        return 'smtp_capability: The server does not support the required TLS or authentication method.'
    if isinstance(error,OSError):
        return 'connection: Could not complete the SMTP connection. Check the host, port and network access.'
    if isinstance(error,ValueError):
        return 'configuration: Check the SMTP port and sender/recipient address format.'
    return 'unclassified: Check SMTP configuration and provider delivery logs.'


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
    parser=argparse.ArgumentParser(description='Send one clearly labeled test email. No account or saved data is changed.')
    parser.add_argument('--to',required=True,help='Your own inbox; Resend testing requires the Resend account email.')
    args=parser.parse_args(argv)
    try:
        send_message(args.to,'Purchase Decision Workspace: email delivery test',
            'This is a requested email-delivery test for Purchase Decision Workspace.\n\n'
            'No account deletion was requested by this test. No saved workspaces or account settings were changed.\n\n'
            'If you can read this message, delivery to this inbox succeeded.\n')
    except Exception as error:
        # Provider exceptions may contain credentials or private recipient data.
        print('Test delivery failed — '+delivery_error(error)+' No account data was changed.')
        return 1
    print('SMTP accepted the test message. Check your inbox and spam folder; acceptance alone does not prove inbox delivery.')
    return 0


if __name__=='__main__':raise SystemExit(main())
