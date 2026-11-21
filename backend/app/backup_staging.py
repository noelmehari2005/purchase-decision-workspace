"""Owner-run staging backup attempt. No .env, scheduled activation or restore."""
from urllib.parse import quote

import certifi
from pymongo import MongoClient

from .backup_archive import BackupError, open_archive
from .backup_capture import capture_archive
from .backup_storage import upload_archive

HOST='pdw-staging.avzq5pq.mongodb.net'
USER='pdw_staging_backup'
DATABASE='pdw_staging'
SOURCE='atlas:6afd0fee51f5c66b18160bf4:pdw_staging'


def encryption_key(value):
    import re
    if not isinstance(value,str) or not re.fullmatch('[0-9a-fA-F]{64}',value):
        raise BackupError('Expected the complete 64-character backup encryption key.')
    return bytes.fromhex(value)


def capture_staging(password,key,*,client_factory=MongoClient,capture=capture_archive):
    """Verify the dedicated principal has exactly the intended read-only role."""
    if not isinstance(password,str) or not password or not isinstance(key,bytes) or len(key)!=32:
        raise BackupError('Backup credentials are incomplete.')
    uri='mongodb+srv://'+USER+':'+quote(password,safe='')+'@'+HOST+'/?authSource=admin&retryWrites=false'
    try:
        with client_factory(uri,tls=True,tlsCAFile=certifi.where(),serverSelectionTimeoutMS=10_000,
                            connectTimeoutMS=10_000,timeoutMS=35_000,appname='pdw-staging-backup-once') as client:
            auth=client.admin.command({'connectionStatus':1,'showPrivileges':False})['authInfo']
            if (auth.get('authenticatedUsers')!=[{'user':USER,'db':'admin'}] or
                    auth.get('authenticatedUserRoles')!=[{'role':'read','db':DATABASE}]):
                raise BackupError('Dedicated read-only backup role was not confirmed.')
            return capture(client[DATABASE],key,SOURCE)
    except BackupError:
        raise
    except Exception:
        raise BackupError('Staging database connection or authentication failed.') from None


def main():
    import argparse
    import getpass
    import json
    import sys

    parser=argparse.ArgumentParser(description='One encrypted staging backup to the dedicated private B2 bucket.')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--capture-and-upload',action='store_true')
    mode.add_argument('--check-capture',action='store_true',help='Read and encrypt in memory only; no B2 upload or saved archive.')
    args=parser.parse_args()
    if not sys.stdin.isatty():
        print('Run interactively in your own Terminal; credentials must not be piped or echoed.')
        return 1
    print('This reads staging users, workspaces, historical reviews and deletion records.')
    print('It encrypts them locally '+('and sends the encrypted archive to the private B2 backup bucket.'
                                      if args.capture_and_upload else 'in memory only; no archive is saved or uploaded.'))
    print('It does not change Atlas data, send email, call Auth0, restore data or schedule future backups.')
    phase='confirmation'
    try:
        confirmation='BACK UP STAGING' if args.capture_and_upload else 'CHECK STAGING CAPTURE'
        if input('Type '+confirmation+' to authorize one attempt: ')!=confirmation:
            print('Cancelled; no network request made.')
            return 1
        phase='credentials'
        key=encryption_key(getpass.getpass('Paste your saved 64-character BACKUP ENCRYPTION key (hidden): '))
        password=getpass.getpass('Paste the NEW pdw_staging_backup DATABASE PASSWORD (hidden): ')
        key_id=getpass.getpass('Paste the restricted B2 keyID (hidden): ') if args.capture_and_upload else None
        app_key=getpass.getpass('Paste its complete B2 applicationKey (hidden): ') if args.capture_and_upload else None
        if not password or (args.capture_and_upload and (not key_id or not app_key)):
            raise BackupError('Backup credentials are incomplete.')
        phase='database-capture'
        blob=capture_staging(password,key)
        if args.check_capture:
            phase='archive-validation'
            payload=open_archive(blob,key)
            print(json.dumps({'source_role_verified':True,'consistent_snapshot_captured':True,
                              'archive_roundtrip_verified':True,'encrypted_bytes':len(blob),
                              'record_counts':{name:len(rows) for name,rows in payload['collections'].items()},
                              'durable_backup_created':False,'uploaded':False}))
            print('Capture check only. No recoverable archive was saved or uploaded.')
            return 0
        phase='b2-upload'
        receipt=upload_archive(blob,key,key_id,app_key)
        print(json.dumps({**{k:receipt[k] for k in ('file_name','bytes','sha256','upload_acknowledged')},
                          'source_role_verified':True,'consistent_snapshot_captured':True,
                          'restore_verified':False,'expiry_verified':False,'recurring_backup_enabled':False}))
        print('Archive upload acknowledged. Preserve your saved encryption key; restore/expiry remain unverified.')
        return 0
    except (EOFError,KeyboardInterrupt):
        print('\nCancelled at '+phase+'. Inspect the B2 bucket before retrying if upload had begun.')
        return 1
    except Exception:
        print('Backup not confirmed at '+phase+'. No source writes were requested. Do not share raw credentials/errors.')
        if phase=='b2-upload':print('B2 may have accepted this attempt. Inspect the bucket before retrying.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
