"""Opt-in server-to-server trigger. No browser, user-token or unsigned access."""
import hashlib
import hmac
import logging
import os
import re
import time
from datetime import datetime,timezone

from fastapi import APIRouter,Request
from pymongo import timeout
from pymongo.errors import DuplicateKeyError

from .runtime import runtime
from .storage_api import configured_repository
from .workspaces import StorageError
from .maintenance import run

router=APIRouter(prefix='/api/v1/maintenance',include_in_schema=False)
PATH='/api/v1/maintenance/run'
WINDOW_SECONDS=120


def authorize(request):
    if not runtime().hosted or os.environ.get('PDW_MAINTENANCE_ENABLED')!='1':
        raise StorageError(404,'not_found','This endpoint is unavailable.')
    secret=os.environ.get('PDW_MAINTENANCE_SECRET','')
    mode=os.environ.get('PDW_MAINTENANCE_MODE','check')
    if not re.fullmatch(r'[0-9a-f]{64}',secret) or mode not in ('check','email-test','notify','cleanup'):
        raise StorageError(503,'maintenance_unconfigured','Maintenance configuration is incomplete.')
    stamp=request.headers.get('x-pdw-timestamp','')
    nonce=request.headers.get('x-pdw-nonce','')
    signature=request.headers.get('x-pdw-signature','')
    if (request.headers.get('origin') is not None or request.url.query or
            not re.fullmatch(r'[0-9]{10}',stamp) or not re.fullmatch(r'[0-9a-f]{32}',nonce) or
            not re.fullmatch(r'[0-9a-f]{64}',signature) or abs(time.time()-int(stamp))>WINDOW_SECONDS):
        raise StorageError(401,'maintenance_denied','The maintenance request was not authorized.')
    message=f'POST\n{PATH}\n{stamp}\n{nonce}'
    expected=hmac.new(secret.encode(),message.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,signature):
        raise StorageError(401,'maintenance_denied','The maintenance request was not authorized.')
    return mode,stamp,nonce


@router.post('/run')
def trigger(request:Request):
    mode,stamp,nonce=authorize(request)  # Reject before any database/provider work.
    try:
        # CSOT bounds DB waits; existing HTTP/SMTP transports have finite timeouts.
        # Work budgets are checked between items; an in-flight send can overrun.
        with timeout(90):
            database=configured_repository().database
            nonces=database.maintenance_nonces
            nonces.create_index('expires_at',expireAfterSeconds=0)
            digest=hashlib.sha256(f'{stamp}:{nonce}'.encode()).hexdigest()
            try:
                nonces.insert_one({'_id':digest,'expires_at':datetime.fromtimestamp(time.time()+300,timezone.utc)})
            except DuplicateKeyError:
                raise StorageError(409,'maintenance_replay','This maintenance request was already used.') from None
            return run(database,mode=mode,limit=1,budget_seconds=35)
    except StorageError:raise
    except Exception as error:
        # Never log credentials, request headers, identities or exception messages.
        logging.getLogger('pdw.maintenance').warning('Maintenance trigger failed: type=%s',type(error).__name__)
        raise StorageError(503,'maintenance_unavailable','Maintenance could not complete. Check the operator diagnostics.') from None
