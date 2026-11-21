"""Bounded encrypted archive and isolated sample-data restore exercise.

No live-database CLI, hosted route, provider calls or automatic backup promise.
"""
from copy import deepcopy
import math
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from urllib.parse import urlsplit
from uuid import uuid4

from bson import BSON
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'PDWBACKUP1\0'
COLLECTIONS=('users','decisions','snapshots','deletion_ledger')
RETENTION_SECONDS=30*86400
MAX_BYTES=32*1024*1024
MAX_ROWS=100_000
STATES=('active','pending_deletion','purging','deleted')
LIFECYCLE=('state','delete_after','delete_requested_at','deletion_id','restored_at')


class BackupError(ValueError):
    pass


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def validate_collections(collections):
    if not isinstance(collections,dict) or set(collections)!=set(COLLECTIONS):
        raise BackupError('Unsupported archive collections.')
    for name,rows in collections.items():
        if not isinstance(rows,list) or len(rows)>MAX_ROWS:
            raise BackupError('Archive row bounds exceeded.')
        ids=set()
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('_id'),str) or row['_id'] in ids:
                raise BackupError('Invalid or duplicate archive record.')
            ids.add(row['_id'])
            if name=='users' and row.get('state') not in STATES:
                raise BackupError('Unknown account state.')
            if name in ('decisions','snapshots'):
                if not isinstance(row.get('owner_id'),str) or not isinstance(row.get('id'),str):
                    raise BackupError('Missing record ownership.')
                expected=row['owner_id']+':'+row['id'] if name=='decisions' else row['owner_id']+':'+str(row.get('decision_id'))+':'+row['id']
                if row['_id']!=expected:raise BackupError('Invalid record ownership key.')
            if name=='deletion_ledger':validate_marker(row)
    owners={row['_id'] for row in collections['users']}
    if any(row['owner_id'] not in owners for name in ('decisions','snapshots') for row in collections[name]):
        raise BackupError('Archive has orphaned ownership.')
    decisions={row['_id'] for row in collections['decisions']}
    if any(row['owner_id']+':'+row['decision_id'] not in decisions for row in collections['snapshots']):
        raise BackupError('Archive has orphaned historical reviews.')


def validate_marker(row):
    owner=row.get('owner_id')
    kind=row.get('kind')
    if not isinstance(owner,str) or kind not in ('account','workspace'):
        raise BackupError('Invalid suppression marker.')
    expected='account:'+owner if kind=='account' else 'workspace:'+owner+':'+str(row.get('decision_id'))
    if row.get('_id')!=expected or (kind=='workspace' and not isinstance(row.get('decision_id'),str)):
        raise BackupError('Invalid suppression marker key.')
    for key in ('active_purged_at','backup_removal_due','delete_after','requested_at'):
        if key in row and not finite(row[key]):raise BackupError('Invalid suppression timestamp.')


def seal(collections,key,source_id,clock=None):
    stamp=time.time() if clock is None else clock
    validate_collections(collections)
    if not isinstance(key,bytes) or len(key)!=32 or not isinstance(source_id,str) or not source_id:
        raise BackupError('Invalid archive key or source identity.')
    if not finite(stamp):raise BackupError('Invalid archive timestamp.')
    payload={'version':1,'source_id':source_id,'created_at':stamp,'expires_at':stamp+RETENTION_SECONDS,
             'collections':collections}
    raw=BSON.encode(payload)
    if len(raw)>MAX_BYTES:raise BackupError('Archive exceeds the bounded prototype size.')
    nonce=secrets.token_bytes(12)
    return MAGIC+nonce+AESGCM(key).encrypt(nonce,raw,MAGIC)


def open_archive(blob,key,clock=None):
    stamp=time.time() if clock is None else clock
    if not isinstance(blob,bytes) or not len(MAGIC)+28<=len(blob)<=MAX_BYTES+len(MAGIC)+28 or not blob.startswith(MAGIC):
        raise BackupError('Invalid archive envelope.')
    if not isinstance(key,bytes) or len(key)!=32:raise BackupError('Invalid archive key.')
    try:
        start=len(MAGIC)
        raw=AESGCM(key).decrypt(blob[start:start+12],blob[start+12:],MAGIC)
        payload=BSON(raw).decode()
    except Exception:
        raise BackupError('Archive authentication or decoding failed.') from None
    if (set(payload)!=set(('version','source_id','created_at','expires_at','collections')) or
            payload['version']!=1 or not isinstance(payload['source_id'],str) or not payload['source_id'] or
            not finite(payload['created_at']) or not finite(payload['expires_at']) or not finite(stamp) or
            payload['expires_at']!=payload['created_at']+RETENTION_SECONDS or payload['created_at']>stamp+30 or
            stamp>=payload['expires_at']):
        raise BackupError('Archive version or validity window rejected.')
    validate_collections(payload['collections'])
    return payload


def restore_plan(payload,controls,clock=None):
    """Apply a fresh, separate current control set before writing any restored data."""
    stamp=time.time() if clock is None else clock
    validate_collections(payload['collections'])
    if not finite(payload.get('expires_at')) or stamp>=payload['expires_at']:
        raise BackupError('Expired archive cannot be restored.')
    if (not isinstance(controls,dict) or controls.get('source_id')!=payload.get('source_id') or
            not finite(controls.get('captured_at')) or not 0<=stamp-controls['captured_at']<=300):
        raise BackupError('A fresh matching control set is required.')
    current={'users':controls.get('users'),'deletion_ledger':controls.get('deletion_ledger'),
             'decisions':[],'snapshots':[]}
    validate_collections(current)
    markers={row['_id']:deepcopy(row) for row in payload['collections']['deletion_ledger']}
    for latest in current['deletion_ledger']:
        old=markers.get(latest['_id'],{})
        merged={**old,**deepcopy(latest)}
        # A newer control copy must never extend an already recorded cutoff.
        for field in ('active_purged_at','backup_removal_due','delete_after'):
            values=[row[field] for row in (old,latest) if field in row]
            if values:merged[field]=min(values)
        markers[latest['_id']]=merged
    users={row['_id']:row for row in current['users']}
    restored=[];allowed=set()
    for original in payload['collections']['users']:
        owner=original['_id'];latest=users.get(owner)
        blocked=not latest or 'account:'+owner in markers or latest['state'] in ('deleted','purging') or original['state'] in ('deleted','purging')
        if latest and latest['state']=='pending_deletion':
            if not finite(latest.get('delete_after')):raise BackupError('Invalid recovery deadline.')
            blocked=blocked or stamp>=latest['delete_after']
        if blocked:
            # Preserve current purge-retry state (including provider subject) in
            # quarantine, rather than turning an unfinished purge into success.
            row=deepcopy(latest) if latest and latest['state'] in ('purging','pending_deletion') else {'_id':owner,'state':'deleted'}
            if 'account:'+owner not in markers:
                markers['account:'+owner]={'_id':'account:'+owner,'kind':'account','owner_id':owner}
                if latest:
                    for field,source in (('delete_after','delete_after'),('requested_at','delete_requested_at')):
                        if finite(latest.get(source)):markers['account:'+owner][field]=latest[source]
        else:
            row=deepcopy(original)
            for field in LIFECYCLE:
                row.pop(field,None)
                if field in latest:row[field]=deepcopy(latest[field])
            allowed.add(owner)
        row['lifecycle_version']=secrets.token_hex(16)
        row.pop('deletion_notice',None)  # Never replay a previously queued email.
        row.pop('purge_lease',None);row.pop('purge_lease_until',None)
        restored.append(row)
    decisions=[]
    for row in payload['collections']['decisions']:
        if row['owner_id'] not in allowed:continue
        if row.get('deleted') is True or 'workspace:'+row['_id'] in markers:
            decisions.append({'_id':row['_id'],'owner_id':row['owner_id'],'id':row['id'],'deleted':True,
                              'deleted_at':row.get('deleted_at',stamp),'revision':row.get('revision',1)})
        else:decisions.append(deepcopy(row))
    visible={row['_id'] for row in decisions if row.get('deleted') is not True}
    snapshots=[deepcopy(row) for row in payload['collections']['snapshots']
               if row['owner_id']+':'+row['decision_id'] in visible]
    result={'users':restored,'decisions':decisions,'snapshots':snapshots,'deletion_ledger':list(markers.values())}
    validate_collections(result)
    return result


def restore_test_database(target,plan,exercise_owner=None):
    """Only a brand-new disposable target can be written by this prototype."""
    if not re.fullmatch(r'pdw_restore_test_[0-9a-f]{32}',target.name):
        raise BackupError('Restore target must be a disposable test database.')
    validate_collections(plan)
    if target.list_collection_names():raise BackupError('Restore target is not empty.')
    # Atomic reservation prevents two operators from restoring into one target.
    target.create_collection('restore_manifest')
    target.restore_manifest.insert_one({'_id':'quarantine','status':'writing','live_access':False,'exercise_owner':exercise_owner})
    try:
        for name in COLLECTIONS:
            if plan[name]:target[name].insert_many(deepcopy(plan[name]))
        from .repositories import MongoRepository
        from .identity import IdentityStore
        from .lifecycle import AccountLifecycle
        MongoRepository(target);IdentityStore(target);AccountLifecycle(target)
        target.restore_manifest.update_one({'_id':'quarantine'},{'$set':{'status':'ready_for_verification'}})
    except Exception:
        target.restore_manifest.update_one({'_id':'quarantine'},{'$set':{'status':'failed'}})
        raise


def local_uri(uri):
    try:parsed=urlsplit(uri)
    except ValueError:raise BackupError('Invalid local test connection.') from None
    if (parsed.scheme!='mongodb' or not re.fullmatch(r'(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?',parsed.netloc) or
            parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment):
        raise BackupError('Only a local disposable MongoDB test connection is permitted.')
    try:port=parsed.port
    except ValueError:raise BackupError('Invalid local test port.') from None
    if port is not None and not 1<=port<=65535:raise BackupError('Invalid local test port.')
    return uri


def sample_workspace():
    """A fictional workspace accepted by the app's real saved-state contract."""
    from .workspaces import WorkspaceState
    laptop={key:'' for key in ('cpu','os','ram','storage','price','tax','shipping','other','provisional',
                               'weight','battery','batteryContext','source','notes')}
    laptop.update(id='current',current=True,name='Fictional current laptop',configuration='Sample build',
                  compatible='yes',costMode='components',price='0',tax='0',shipping='0',other='0')
    candidate={**laptop,'id':'candidate','current':False,'name':'Fictional candidate','price':'800','ram':'16','storage':'512'}
    return WorkspaceState.model_validate({
        'schemaVersion':1,'title':'FICTIONAL restore sample','timezone':'America/Los_Angeles','tasks':[],
        'customNeeds':'Sample data only','requirements':{'ram':'16','storage':'512','ceiling':'900','noLimit':False,'compatibility':True},
        'preferences':{},'records':[{'draft':laptop,'confirmed':laptop,'revision':1},
                                  {'draft':candidate,'confirmed':candidate,'revision':2}],
        'plan':{'savings':'300','contribution':'150','firstDate':'2027-01-31','targetDate':'2027-03-31',
                'essential':False,'useBudget':True,'income':'1600','housing':'700','food':'250','transportation':'180',
                'other':'120','goals':'150','buffer':'50','useScenario':False,'category':'transportation',
                'reduction':'0','allocation':'0'},'outcome':'Investigate and save','reason':'Fictional backup fixture.'
    }).model_dump()


def exercise(uri):
    """Create fixtures, encrypt, restore with newer controls, verify, remove fixtures."""
    from pymongo import MongoClient
    from .repositories import MongoRepository
    from .workspaces import StorageError,WorkspaceState,now
    client=MongoClient(local_uri(uri),serverSelectionTimeoutMS=3000,timeoutMS=10000)
    suffix=uuid4().hex;source=client['pdw_backup_test_'+suffix];target=client['pdw_restore_test_'+suffix]
    stamp=time.time();key=AESGCM.generate_key(bit_length=256);source_owned=False;target_owned=False
    try:
        client.admin.command('ping')
        if source.list_collection_names() or target.list_collection_names():raise BackupError('Fixture database collision.')
        source.create_collection('fixture_manifest')
        source.fixture_manifest.insert_one({'_id':suffix})
        source_owned=True
        source.users.insert_many([{'_id':owner,'state':'active','subject':'fixture|'+owner,'email':owner+'@example.invalid'}
                                  for owner in ('owner_a','owner_b','owner_c')])
        source.decisions.insert_many([{'_id':owner+':'+ident,'owner_id':owner,'id':ident,'revision':3,
            'schema_version':1,'created_at':now(),'updated_at':now(),'state':sample_workspace()}
            for owner,ident in (('owner_a','keep'),('owner_a','gone'),('owner_b','private'),('owner_c','expired'))])
        source.snapshots.insert_many([{'_id':row['_id']+':review','owner_id':row['owner_id'],'decision_id':row['id'],
            'id':'review','decision_revision':3,'created_at':now(),'state':row['state']} for row in source.decisions.find({})])
        source.app_sessions.insert_one({'_id':'fake-bearer-session','owner_id':'owner_a'})
        source.login_flows.insert_one({'_id':'fake-login-flow'})
        collections={name:list(source[name].find({})) for name in COLLECTIONS}
        blob=seal(collections,key,source.name,clock=stamp)
        with tempfile.TemporaryDirectory(prefix='pdw_backup_fixture_') as folder:
            path=Path(folder)/'sample.pdwbackup'
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as output:output.write(blob)
            payload=open_archive(path.read_bytes(),key,clock=stamp)
            # New deletion decisions must take precedence over the older archive.
            source.deletion_ledger.insert_many([
                {'_id':'account:owner_b','kind':'account','owner_id':'owner_b','active_purged_at':stamp,
                 'backup_removal_due':stamp+RETENTION_SECONDS},
                {'_id':'workspace:owner_a:gone','kind':'workspace','owner_id':'owner_a','decision_id':'gone'}])
            source.users.update_one({'_id':'owner_b'},{'$set':{'state':'deleted'}})
            source.users.update_one({'_id':'owner_c'},{'$set':{'state':'pending_deletion','delete_after':stamp,
                                                               'delete_requested_at':stamp-RETENTION_SECONDS}})
            controls={'source_id':source.name,'captured_at':stamp,'users':list(source.users.find({})),
                      'deletion_ledger':list(source.deletion_ledger.find({}))}
            before={name:list(source[name].find({}).sort('_id',1)) for name in (*COLLECTIONS,'app_sessions','login_flows')}
            target_owned=True  # Cleanup below also requires the matching reservation marker.
            restore_test_database(target,restore_plan(payload,controls,clock=stamp),exercise_owner=suffix)
            repo=MongoRepository(target)
            expected=next(row for row in collections['decisions'] if row['_id']=='owner_a:keep')
            if repo.get('owner_a','keep')['state']!=expected['state']:
                raise BackupError('Saved workspace comparison failed.')
            WorkspaceState.model_validate(repo.get('owner_a','keep')['state'])
            if repo.get('owner_a','keep')['revision']!=3 or len(repo.list_snapshots('owner_a','keep',0,10))!=1:
                raise BackupError('Workspace revisions or historical review listing changed.')
            for owner,ident in (('owner_a','gone'),('owner_b','private'),('owner_c','expired'),('owner_b','keep')):
                try:repo.get(owner,ident)
                except StorageError as error:
                    if error.status!=404:raise
                else:raise BackupError('Suppressed data became visible.')
            if target.snapshots.count_documents({})!=1 or target.app_sessions.count_documents({}) or target.login_flows.count_documents({}):
                raise BackupError('Restore isolation check failed.')
            if any(list(source[name].find({}).sort('_id',1))!=rows for name,rows in before.items()):
                raise BackupError('Source was modified by restore.')
            target.restore_manifest.update_one({'_id':'quarantine'},{'$set':{'status':'verified_sample_restore'}})
        return {'status':'ok','fixture_workspaces':4,'restored_visible_workspaces':1,
                'restored_reviews':1,'restored_sessions':0,'current_deletions_applied':True,
                'source_unchanged_by_restore':True,'durable_live_backup_created':False}
    finally:
        # Only these randomly named, explicitly disposable fixture databases.
        try:
            if source_owned and source.fixture_manifest.find_one({'_id':suffix}):client.drop_database(source.name)
            if target_owned and target.restore_manifest.find_one({'_id':'quarantine','exercise_owner':suffix}):client.drop_database(target.name)
        finally:client.close()


def main(argv=None):
    import argparse,json
    parser=argparse.ArgumentParser(description='Isolated encrypted backup/restore exercise using fictional local data only.')
    parser.add_argument('--exercise',action='store_true',required=True)
    parser.add_argument('--uri',default='mongodb://127.0.0.1:27017')
    args=parser.parse_args(argv)
    try:result=exercise(args.uri)
    except Exception:
        print(json.dumps({'status':'failed','message':'Backup exercise failed; no hosted database was targeted.'}))
        return 1
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
