"""Signed opt-in backup trigger, distinct from account maintenance."""
import hashlib
import os
import time
from datetime import datetime,timezone

from fastapi import APIRouter,Request
from pymongo.errors import DuplicateKeyError

from .maintenance_api import authorize
from .storage_api import configured_repository
from .backup_job import run_daily
from .workspaces import StorageError

router=APIRouter(prefix='/api/v1/backups',include_in_schema=False)
PATH='/api/v1/backups/run'


@router.post('/run')
def trigger(request:Request):
    if os.environ.get('PDW_BACKUP_ENABLED')!='1':
        raise StorageError(404,'not_found','This endpoint is unavailable.')
    secret=os.environ.get('PDW_BACKUP_SIGNING_SECRET','')
    if secret and secret.casefold() in (os.environ.get('PDW_BACKUP_ENCRYPTION_KEY','').casefold(),
                                        os.environ.get('PDW_MAINTENANCE_SECRET','').casefold()):
        raise StorageError(503,'backup_unconfigured','Use a separate backup signing secret.')
    _,stamp,nonce=authorize(request,path=PATH,enabled_env='PDW_BACKUP_ENABLED',secret_env='PDW_BACKUP_SIGNING_SECRET',mode_env=None)
    try:
        database=configured_repository().database
        nonces=database.maintenance_nonces
        nonces.create_index('expires_at',expireAfterSeconds=0)
        try:
            nonces.insert_one({'_id':hashlib.sha256(f'{stamp}:{nonce}'.encode()).hexdigest(),
                              'expires_at':datetime.fromtimestamp(time.time()+300,timezone.utc)})
        except DuplicateKeyError:
            raise StorageError(409,'backup_replay','This backup request was already used.') from None
        return run_daily(database)
    except StorageError:
        raise
    except Exception:
        raise StorageError(503,'backup_unavailable','The backup service could not complete. Check the operator status.') from None
