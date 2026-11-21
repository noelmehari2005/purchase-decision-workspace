"""Bounded B2 archive transport; no scheduler, credential loading or live capture.

Only authenticated PDW archives can be uploaded. The encryption key stays local.
An upload acknowledgement is not a restore proof or retention verification.
"""
import hashlib
import re
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .backup_archive import BackupError, open_archive

BUCKET_ID='dda850c39930f979ac190c13'
BUCKET_NAME='pdw-staging-backups-noelmehari-20261119'
PREFIX='archives/'
AUTHORIZE='https://api.backblazeb2.com/b2api/v4/b2_authorize_account'
MAX_RESPONSE_BYTES=64*1024


class BackupStorageError(ValueError):
    """Safe fixed error text; never include provider bodies, URLs or credentials."""


def _endpoint(value, upload=False):
    if not isinstance(value,str):
        raise BackupStorageError('Backup storage endpoint rejected.')
    parsed=urlsplit(value)
    host_pattern=r'pod-[a-z0-9-]+\.backblaze(?:b2)?\.com' if upload else r'api[0-9]+\.backblazeb2\.com'
    if (parsed.scheme!='https' or not re.fullmatch(host_pattern,parsed.netloc) or
            parsed.fragment or (not upload and (parsed.path not in ('','/') or parsed.query)) or
            (upload and not re.fullmatch(r'/b2api/v4/b2_upload_file(?:/[a-zA-Z0-9_-]+)*',parsed.path))):
        raise BackupStorageError('Backup storage endpoint rejected.')
    return value.rstrip('/') if not upload else value


def _token(value):
    if not isinstance(value,str) or not value or len(value)>8192 or any(ord(c)<33 or ord(c)>126 for c in value):
        raise BackupStorageError('Backup storage credential rejected.')
    return value


def _json(client,method,url,**kwargs):
    try:
        with client.stream(method,url,**kwargs) as response:
            if response.status_code!=200:
                raise BackupStorageError('Backup storage request failed.')
            chunks=[];size=0
            for part in response.iter_bytes():
                size+=len(part)
                if size>MAX_RESPONSE_BYTES:
                    raise BackupStorageError('Backup storage response rejected.')
                chunks.append(part)
            import json
            result=json.loads(b''.join(chunks))
            if not isinstance(result,dict):
                raise BackupStorageError('Backup storage response rejected.')
            return result
    except BackupStorageError:
        raise
    except Exception:
        raise BackupStorageError('Backup storage request failed.') from None


def upload_archive(blob,encryption_key,key_id,application_key,*,client_factory=httpx.Client,clock=None):
    """Upload once to the dedicated staging bucket, returning a checked receipt.

    No retries: a timeout may mean B2 accepted the file. Operators must inspect
    that attempt before retrying. Provider-native checksums supplement AES-GCM;
    SHA-1 here is B2's transport field, not the archive's security mechanism.
    """
    try:
        open_archive(blob,encryption_key,clock=clock)
    except BackupError:
        raise BackupStorageError('Backup archive rejected before upload.') from None
    _token(key_id);_token(application_key)
    name=PREFIX+uuid4().hex+'.pdwbackup'
    checksum=hashlib.sha1(blob).hexdigest()
    try:
        with client_factory(timeout=httpx.Timeout(30,connect=10),follow_redirects=False,trust_env=False) as client:
            auth=_json(client,'GET',AUTHORIZE,auth=httpx.BasicAuth(key_id,application_key))
            storage=auth['apiInfo']['storageApi'];allowed=storage['allowed']
            # Refuse account-wide or other-bucket keys. No permission mutation.
            buckets=allowed['buckets']
            if (not isinstance(buckets,list) or len(buckets)!=1 or buckets[0].get('id')!=BUCKET_ID or
                    buckets[0].get('name')!=BUCKET_NAME or allowed.get('namePrefix')!=PREFIX or
                    not isinstance(allowed.get('capabilities'),list) or
                    'writeFiles' not in allowed['capabilities'] or
                    not set(allowed['capabilities']).issubset({'listBuckets','writeFiles'})):
                raise BackupStorageError('Backup storage key scope rejected.')
            api=_endpoint(storage['apiUrl'])
            upload=_json(client,'POST',api+'/b2api/v4/b2_get_upload_url',
                         headers={'Authorization':_token(auth['authorizationToken'])},json={'bucketId':BUCKET_ID})
            if upload.get('bucketId')!=BUCKET_ID:
                raise BackupStorageError('Backup storage bucket rejected.')
            result=_json(client,'POST',_endpoint(upload['uploadUrl'],upload=True),
                         headers={'Authorization':_token(upload['authorizationToken']),
                                  'X-Bz-File-Name':name,'Content-Type':'application/octet-stream',
                                  'X-Bz-Content-Sha1':checksum,'X-Bz-Server-Side-Encryption':'AES256'},content=blob)
            if (result.get('bucketId')!=BUCKET_ID or result.get('fileName')!=name or
                    type(result.get('contentLength')) is not int or result['contentLength']!=len(blob) or
                    result.get('contentSha1')!=checksum or not isinstance(result.get('fileId'),str) or not result['fileId']):
                raise BackupStorageError('Backup storage acknowledgement rejected.')
            return {'file_name':name,'file_id':result['fileId'],'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
                    'upload_acknowledged':True,'restore_verified':False,'expiry_verified':False,
                    'key_expires_at':auth.get('applicationKeyExpirationTimestamp')}
    except BackupStorageError:
        raise
    except Exception:
        raise BackupStorageError('Backup storage request failed.') from None


def main():
    """Owner-run transport probe: fictional data, hidden key entry, no .env."""
    import argparse
    import getpass
    import json
    import secrets
    import sys
    from .backup_archive import COLLECTIONS, seal

    parser=argparse.ArgumentParser(description='Upload one encrypted fictional B2 fixture; never reads MongoDB.')
    parser.add_argument('--upload-fixture',action='store_true',required=True)
    parser.parse_args()
    print('Destination: '+BUCKET_NAME+' / archives/ (one small fictional encrypted object).')
    if input('Type UPLOAD FIXTURE to authorize this upload: ')!='UPLOAD FIXTURE':
        print('Cancelled; no network request made.')
        return 1
    try:
        key_id=getpass.getpass('Paste the restricted B2 keyID (hidden), then press Return: ')
        app_key=getpass.getpass('Paste its complete applicationKey (hidden), then press Return: ')
        rows={name:[] for name in COLLECTIONS}
        rows['users']=[{'_id':'fictional-backup-probe','state':'active','email':'probe@example.invalid'}]
        encryption_key=secrets.token_bytes(32)
        blob=seal(rows,encryption_key,'fictional-storage-probe')
        receipt=upload_archive(blob,encryption_key,key_id,app_key)
        print(json.dumps({k:receipt[k] for k in ('file_name','bytes','sha256','upload_acknowledged','restore_verified','expiry_verified')}))
        print('Fixture only: its temporary encryption key is discarded. No app data was backed up.')
        return 0
    except (EOFError,KeyboardInterrupt):
        print('\nCancelled. If an upload had started, inspect the bucket before retrying.')
        return 1
    except Exception:
        print('Upload not confirmed. Inspect the bucket before retrying; do not share credentials or raw errors.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
