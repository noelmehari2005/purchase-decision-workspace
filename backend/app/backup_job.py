"""Opt-in daily encrypted upload, with no restore, email or deletion behavior."""
from datetime import datetime, timezone
import math
import os
import time

from pymongo.errors import DuplicateKeyError

from .backup_staging import capture_staging, encryption_key
from .backup_storage import upload_archive, _token
from .maintenance_lease import MaintenanceLease
from .workspaces import StorageError


def run_daily(database,*,environ=None,clock=time.time,capture=capture_staging,upload=upload_archive,lease_factory=MaintenanceLease):
    env=os.environ if environ is None else environ
    if env.get('PDW_BACKUP_ENABLED')!='1':return {'status':'disabled','mode':'backup','uploaded':False}
    try:
        key=encryption_key(env.get('PDW_BACKUP_ENCRYPTION_KEY'))
        password=env.get('PDW_BACKUP_MONGO_PASSWORD')
        if not isinstance(password,str) or not password or len(password)>1024 or '\0' in password:
            raise ValueError('Invalid database password.')
        key_id=_token(env.get('PDW_BACKUP_WRITER_KEY_ID'))
        app_key=_token(env.get('PDW_BACKUP_WRITER_APPLICATION_KEY'))
    except Exception:
        raise StorageError(503,'backup_unconfigured','Backup configuration is incomplete.') from None
    lease=lease_factory(database,name='backup')
    if not lease.acquire():return {'status':'busy','mode':'backup','uploaded':False}
    try:
        stamp=clock();day=datetime.fromtimestamp(stamp,timezone.utc).strftime('%Y-%m-%d')
        record_id='backup_run_'+day
        try:
            # Claim before any source capture/upload. An ambiguous upload is
            # never repeated automatically on the same UTC date.
            database.system_status.insert_one({'_id':record_id,'status':'attempted','started_at':stamp})
        except DuplicateKeyError:
            return {'status':'already_attempted','mode':'backup','uploaded':False}
        phase='capture'
        try:
            lease.renew();blob=capture(password,key)
            lease.renew();phase='upload'
            receipt=upload(blob,key,key_id,app_key)
            lease.renew();expires=receipt.get('key_expires_at')
            # Tokens may authenticate while approaching expiry: keep uploading,
            # but withhold a healthy heartbeat so the operator is warned.
            rotation_due=(type(expires) not in (int,float) or not math.isfinite(expires) or
                          expires/1000<clock()+14*86400)
            database.system_status.update_one({'_id':record_id},{'$set':{
                'status':'attention' if rotation_due else 'accepted','finished_at':clock(),
                'file_name':receipt['file_name'],'sha256':receipt['sha256'],'bytes':receipt['bytes'],
                'writer_rotation_due':rotation_due,
                'writer_key_expires_at':expires/1000 if type(expires) in (int,float) and math.isfinite(expires) else None}})
            return {'status':'attention' if rotation_due else 'ok','mode':'backup','uploaded':True,
                    'writer_rotation_due':rotation_due}
        except Exception:
            database.system_status.update_one({'_id':record_id},{'$set':{
                'status':'failed','finished_at':clock(),'phase':phase}})
            raise StorageError(503,'backup_failed','The backup attempt was not confirmed. Inspect the operator status before retrying.') from None
    finally:
        lease.release()
