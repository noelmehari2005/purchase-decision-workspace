"""Explicit, freshly authenticated account deletion and restoration."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Request
from fastapi.responses import JSONResponse
from .schemas import Contract
from .workspaces import StorageError
from . import auth_api
from .auth_provider import auth_mode
from .storage_api import safe_operation
from .lifecycle import AccountLifecycle,fresh,status

router=APIRouter(prefix='/api/v1/account')

class DeleteAccount(Contract):
    request_id:UUID
    confirmation:Literal['DELETE MY ACCOUNT']


def actor(request,require_fresh=False):
    auth_api.allowed_origin(request)
    if not auth_api.runtime().hosted and request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
        raise StorageError(403,'local_only','This milestone supports local development only.')
    if auth_mode()!='auth0':raise StorageError(403,'account_required','Account deletion requires a signed-in account.')
    record,user=auth_api.checked_session(request,auth_api.identity_store(),auth_api.provider(),allow_pending=True)
    if request.method!='GET':auth_api.csrf_check(request,record)
    if user.get('email_verified') is not True:
        raise StorageError(403,'email_unverified','Verify your email before changing account settings.')
    if require_fresh:fresh(record)
    return record,user


def lifecycle():
    from .storage_api import configured_repository
    return AccountLifecycle(configured_repository().database)


def clear_session(body):
    response=JSONResponse(body)
    response.delete_cookie(auth_api.SESSION_COOKIE,path='/',httponly=True,samesite='lax')
    return response

@router.get('/lifecycle')
def account_status(request:Request):
    _,user=actor(request)
    return status(user)

@router.post('/deletion-request')
def request_deletion(request:Request,payload:DeleteAccount):
    _,user=actor(request,True)
    result=safe_operation(lambda:lifecycle().request(user,payload.request_id))
    return clear_session({**result,'signed_out':True})

@router.post('/restore')
def restore(request:Request):
    record,user=actor(request,True)
    result=safe_operation(lambda:lifecycle().restore(user))
    from datetime import datetime,timezone
    version=record.get('credential_version')
    changed=datetime.fromtimestamp(version,timezone.utc).isoformat() if version is not None else None
    source=auth_api.provider()
    token=auth_api.identity_store().create_session(source.config.issuer,user['subject'],user['email'],True,
        record['auth_time'],password_changed_at=changed)
    if auth_api.runtime().hosted:
        return JSONResponse({**result,'session_token':token})
    response=JSONResponse(result)
    response.set_cookie(auth_api.SESSION_COOKIE,token,max_age=86400,httponly=True,samesite='lax',secure=source.config.secure,path='/')
    return response
