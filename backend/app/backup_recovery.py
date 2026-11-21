"""Owner-run download and isolated restore drill. Never restores into Atlas."""
import hashlib
import re
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pymongo import MongoClient

from .backup_archive import (BackupError, COLLECTIONS, MAGIC, MAX_BYTES, local_uri,
                             open_archive, restore_plan, restore_test_database)
from .backup_staging import SOURCE, capture_staging, encryption_key
from .backup_storage import AUTHORIZE, BUCKET_ID, BUCKET_NAME, PREFIX, BackupStorageError, _json, _token


def authorize_reader(client,key_id,application_key):
    _token(key_id);_token(application_key)
    auth=_json(client,'GET',AUTHORIZE,auth=httpx.BasicAuth(key_id,application_key))
    storage=auth['apiInfo']['storageApi'];allowed=storage['allowed']
    if (allowed.get('buckets')!=[{'id':BUCKET_ID,'name':BUCKET_NAME}] or
            allowed.get('namePrefix')!=PREFIX or not isinstance(allowed.get('capabilities'),list) or
            set(allowed['capabilities'])!={'listBuckets','listFiles','readFiles'}):
        raise BackupStorageError('Dedicated read-only archive key scope rejected.')
    _token(auth['authorizationToken'])
    return auth,storage


def download_archive(file_name,expected_sha256,key_id,application_key,*,client_factory=httpx.Client):
    if (not isinstance(file_name,str) or not re.fullmatch(r'archives/[0-9a-f]{32}\.pdwbackup',file_name) or
            not isinstance(expected_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',expected_sha256)):
        raise BackupStorageError('Archive name or expected checksum rejected.')
    _token(key_id);_token(application_key)
    try:
        with client_factory(timeout=httpx.Timeout(30,connect=10),follow_redirects=False,trust_env=False) as client:
            auth,storage=authorize_reader(client,key_id,application_key)
            base=storage['downloadUrl'];parsed=urlsplit(base)
            if (parsed.scheme!='https' or not re.fullmatch(r'f[0-9]+\.backblazeb2\.com',parsed.netloc) or
                    parsed.path not in ('','/') or parsed.query or parsed.fragment):
                raise BackupStorageError('Archive download endpoint rejected.')
            url=base.rstrip('/')+'/file/'+BUCKET_NAME+'/'+file_name
            with client.stream('GET',url,headers={'Authorization':_token(auth['authorizationToken'])}) as response:
                if response.status_code!=200:raise BackupStorageError('Archive download failed.')
                chunks=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>MAX_BYTES+len(MAGIC)+28:raise BackupStorageError('Archive download bounds exceeded.')
                    chunks.append(chunk)
                blob=b''.join(chunks)
            if hashlib.sha256(blob).hexdigest()!=expected_sha256:
                raise BackupStorageError('Downloaded archive checksum mismatch.')
            return blob
    except BackupStorageError:
        raise
    except Exception:
        raise BackupStorageError('Archive download failed.') from None


def verify_local_restore(target,plan):
    from .repositories import MongoRepository
    from .workspaces import StorageError, WorkspaceState
    for name in COLLECTIONS:
        actual=list(target[name].find({}).sort('_id',1))
        expected=sorted(plan[name],key=lambda row:row['_id'])
        if actual!=expected:raise BackupError('Restored records differ from the suppression plan.')
    if target.app_sessions.count_documents({}) or target.login_flows.count_documents({}):
        raise BackupError('Transient authentication records were restored.')
    repo=MongoRepository(target)
    visible=0
    for row in plan['decisions']:
        if row.get('deleted'):
            try:repo.get(row['owner_id'],row['id'])
            except StorageError as error:
                if error.status!=404:raise
            else:raise BackupError('Suppressed workspace became visible.')
            continue
        saved=repo.get(row['owner_id'],row['id'])
        WorkspaceState.model_validate(saved['state'])
        if saved['state']!=row['state'] or saved['revision']!=row['revision']:
            raise BackupError('Workspace state or revision changed.')
        try:repo.get('backup-drill-unrelated-owner',row['id'])
        except StorageError as error:
            if error.status!=404:raise
        else:raise BackupError('Cross-owner workspace access was allowed.')
        visible+=1
    for row in plan['snapshots']:
        saved=repo.find_snapshot(row['owner_id'],row['decision_id'],row['id'])
        if saved!={k:v for k,v in row.items() if k not in ('_id','owner_id')}:
            raise BackupError('Historical review retrieval changed.')
    return visible


def restore_local(payload,controls,*,uri='mongodb://127.0.0.1:27017',client_factory=MongoClient):
    safe_uri=local_uri(uri)
    if payload.get('source_id')!=SOURCE:raise BackupError('Unexpected archive source.')
    plan=restore_plan(payload,controls)
    suffix=uuid4().hex;owner=uuid4().hex;name='pdw_restore_test_'+suffix
    with client_factory(safe_uri,serverSelectionTimeoutMS=3000,timeoutMS=30_000) as client:
        client.admin.command('ping')
        target=client[name];reserved=False
        try:
            if target.list_collection_names():raise BackupError('Disposable restore target already exists.')
            reserved=True
            restore_test_database(target,plan,exercise_owner=owner)
            visible=verify_local_restore(target,plan)
            result={'restore_verified':True,'restored_visible_workspaces':visible,
                    'restored_reviews':len(plan['snapshots']),'restored_sessions':0,
                    'current_controls_applied':True,'live_access_enabled':False,
                    'atlas_writes_requested':False,'expiry_verified':False,'recurring_backup_enabled':False}
        finally:
            # Only the new random local target bearing this attempt's reservation.
            if reserved:
                if target.restore_manifest.find_one({'_id':'quarantine','exercise_owner':owner}):
                    client.drop_database(name)
                else:
                    raise BackupError('Disposable target ownership/cleanup was not confirmed.')
        result['disposable_target_removed']=True
        return result


def main():
    import argparse
    import getpass
    import json
    import sys
    parser=argparse.ArgumentParser(description='Download one encrypted archive and verify a disposable local restore.')
    parser.add_argument('--file',required=True)
    parser.add_argument('--sha256',required=True)
    args=parser.parse_args()
    if not sys.stdin.isatty():
        print('Run interactively in your own Terminal with hidden credential input.')
        return 1
    print('Downloads/decrypts this archive, reads current Atlas deletion controls, and restores only into a NEW disposable local database.')
    print('The temporary restored database is removed after the check. Atlas and the B2 archive are never modified.')
    phase='confirmation'
    try:
        if input('Type RESTORE LOCAL DRILL to authorize this disposable test: ')!='RESTORE LOCAL DRILL':
            print('Cancelled; no request made.');return 1
        phase='credentials'
        key=encryption_key(getpass.getpass('Saved 64-character BACKUP ENCRYPTION key (hidden): '))
        password=getpass.getpass('pdw_staging_backup DATABASE PASSWORD (hidden): ')
        key_id=getpass.getpass('B2 READER keyID (hidden): ')
        application_key=getpass.getpass('B2 READER applicationKey (hidden): ')
        phase='download'
        blob=download_archive(args.file,args.sha256,key_id,application_key)
        phase='archive-authentication'
        payload=open_archive(blob,key)
        if payload['source_id']!=SOURCE:raise BackupError('Unexpected archive source.')
        phase='current-controls'
        current=open_archive(capture_staging(password,key),key)
        controls={'source_id':current['source_id'],'captured_at':current['created_at'],
                  'users':current['collections']['users'],'deletion_ledger':current['collections']['deletion_ledger']}
        phase='local-restore-and-cleanup'
        result=restore_local(payload,controls)
        print(json.dumps({'download_sha256_verified':True,'archive_authenticated':True,**result}))
        return 0
    except (EOFError,KeyboardInterrupt):
        print('\nDrill stopped at '+phase+'. No live source writes were requested.');return 1
    except Exception:
        print('Drill not confirmed at '+phase+'. No live source writes were requested.')
        if phase=='local-restore-and-cleanup':print('A local quarantined test database may remain; do not connect the app to it.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
