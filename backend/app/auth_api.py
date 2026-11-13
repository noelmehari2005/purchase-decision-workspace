"""Email/password OIDC routes and verified, server-derived ownership."""
import logging
import os
import secrets
import time
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter,Depends,Request
from fastapi.responses import JSONResponse,RedirectResponse
from pydantic import Field,field_validator
from starlette.concurrency import run_in_threadpool

from .auth_provider import auth_mode,provider,settings
from .identity import IdentityStore,IDLE_SECONDS
from .schemas import Contract
from .workspaces import StorageError

SESSION_COOKIE='pdw_session'
FLOW_COOKIE='pdw_login'
router=APIRouter(prefix='/api/v1/auth')


@lru_cache(maxsize=1)
def identity_store():
    from .storage_api import configured_repository
    try:return IdentityStore(configured_repository().database)
    except Exception as error:
        raise StorageError(503,'identity_unavailable','Cannot reach account storage. Check the local database.') from error


def allowed_origin(request):
    origin=request.headers.get('origin')
    expected=os.environ.get('PDW_APP_ORIGIN','http://127.0.0.1:5173').rstrip('/')
    if origin and origin!=expected:
        raise StorageError(403,'invalid_origin','This origin cannot access your workspace.')


def csrf_check(request,session):
    allowed_origin(request)
    if not secrets.compare_digest(request.headers.get('x-pdw-csrf',''),session['csrf']):
        raise StorageError(403,'csrf_required','Refresh your session before making changes.')


def checked_session(request,store,source):
    from pymongo.errors import PyMongoError
    try:
        record,user=store.session(request.cookies.get(SESSION_COOKIE))
        user=store.refresh_profile(user,source.profile(user['subject']),record)
        return record,user
    except PyMongoError as error:
        raise StorageError(503,'identity_unavailable','Cannot verify your session right now. Saved records are unchanged.') from error


def current_owner(request:Request):
    allowed_origin(request)
    if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
        raise StorageError(403,'local_only','This milestone supports local development only.')
    if auth_mode()=='local':
        # Explicit legacy test mode, never an automatic fallback on auth failure.
        if os.environ.get('PDW_LOCAL_STORAGE')!='1':
            raise StorageError(503,'storage_disabled','Local storage is not enabled.')
        return 'local-development-user'
    source=provider()
    record,user=checked_session(request,identity_store(),source)
    if request.method not in ('GET','HEAD','OPTIONS'):csrf_check(request,record)
    if user['email_verified'] is not True:
        raise StorageError(403,'email_unverified','Verify your email before accessing saved workspaces.')
    return user['_id']


@router.get('/session')
def session_status(request:Request):
    allowed_origin(request)
    if auth_mode()=='local':return {'mode':'local','configured':False,'authenticated':False}
    try:source=provider()
    except StorageError as error:
        if error.code in ('auth_unconfigured','auth_dependencies_missing'):return {'mode':'auth0','configured':False,'authenticated':False}
        raise
    if not request.cookies.get(SESSION_COOKIE):return {'mode':'auth0','configured':True,'authenticated':False}
    record,user=checked_session(request,identity_store(),source)
    return {'mode':'auth0','configured':True,'authenticated':True,'verified':user['email_verified'],
        'user':{'id':user['_id'],'email':user['email']},'csrf':record['csrf'],
        'idle_until':record['last_active']+IDLE_SECONDS,'absolute_until':record['absolute_until']}


@router.get('/login')
@router.get('/signup')
async def begin_login(request:Request):
    allowed_origin(request)
    source=provider()
    store=identity_store()
    await run_in_threadpool(store.rate_limit,'login:'+request.client.host,20,600)
    decision=request.query_params.get('decision','')
    if decision:
        try:request.session['return_decision']=str(UUID(decision))
        except ValueError:pass
    try:return await source.login(request,request.url.path.endswith('/signup'))
    except Exception:
        # Never put provider messages, tokens, or user-supplied error descriptions in URLs.
        return RedirectResponse(source.config.origin+'/?auth_error=signin_failed',status_code=303)


@router.get('/callback')
async def callback(request:Request):
    source=provider()
    store=identity_store()
    decision=request.session.get('return_decision')
    stage='oidc_validation'
    try:
        claims=await source.claims(request)
        subject=claims['sub']
        stage='account_profile'
        profile=await run_in_threadpool(source.profile,subject)
        if profile.get('user_id')!=subject or profile.get('blocked') is True:raise ValueError('Unavailable identity')
        email=profile.get('email')
        if not isinstance(email,str) or not email or len(email)>320:raise ValueError('Missing identity')
        old=request.cookies.get(SESSION_COOKIE)
        if old:await run_in_threadpool(store.revoke,old)
        stage='application_session'
        token=await run_in_threadpool(store.create_session,source.config.issuer,subject,email,
                                      profile.get('email_verified') is True,claims['auth_time'],password_changed_at=profile.get('last_password_reset'))
        location=source.config.origin+'/'
        if decision:location+='?decision='+str(UUID(decision))
        response=RedirectResponse(location,status_code=303)
        response.set_cookie(SESSION_COOKIE,token,max_age=86400,httponly=True,samesite='lax',secure=source.config.secure,path='/')
        return response
    except Exception as error:
        cause=error.__cause__ or error
        status=getattr(getattr(cause,'response',None),'status_code',None)
        logging.getLogger('pdw.auth').warning('Sign-in failed: stage=%s type=%s provider_status=%s',stage,type(error).__name__,status)
        return RedirectResponse(source.config.origin+'/?auth_error=signin_failed',status_code=303)
    finally:request.session.clear()


@router.post('/activity')
def activity(request:Request):
    record,_user=checked_session(request,identity_store(),provider())
    csrf_check(request,record)
    identity_store().touch(request.cookies.get(SESSION_COOKIE))
    return {'idle_until':min(time.time()+IDLE_SECONDS,record['absolute_until'])}


@router.post('/logout')
def logout(request:Request):
    allowed_origin(request)
    store=identity_store()
    token=request.cookies.get(SESSION_COOKIE)
    try:record,_=store.session(token)
    except StorageError as error:
        if error.status!=401:raise
    else:csrf_check(request,record)
    store.revoke(token)
    response=JSONResponse({'signed_out':True})
    response.delete_cookie(SESSION_COOKIE,path='/',httponly=True,samesite='lax')
    return response


class ResetRequest(Contract):
    email:Annotated[str,Field(min_length=3,max_length=320)]
    @field_validator('email')
    @classmethod
    def email_shape(cls,value):
        value=value.strip()
        if '@' not in value or any(c.isspace() for c in value):raise ValueError('Enter your email address.')
        return value


@router.post('/password-reset',status_code=202)
def password_reset(request:Request,payload:ResetRequest):
    allowed_origin(request)
    store=identity_store()
    store.rate_limit('reset-ip:'+request.client.host,5,600)
    store.rate_limit('reset-email:'+payload.email.casefold(),3,600)
    source=provider()
    try:source.request_reset(payload.email)
    except Exception:pass
    # Same response whether an account exists, the provider refuses it, or email delivery fails.
    return {'message':'If an eligible account exists, password-reset instructions may arrive by email. Check your inbox and spam folder.'}


class AuthLogFilter(logging.Filter):
    def filter(self,record):
        if isinstance(record.args,tuple) and len(record.args)>=3 and isinstance(record.args[2],str) and '/api/v1/auth/' in record.args[2]:
            args=list(record.args);args[2]=args[2].split('?')[0];record.args=tuple(args)
        return True


def install_auth(app):
    app.include_router(router)
    logging.getLogger('uvicorn.access').addFilter(AuthLogFilter())

    @app.middleware('http')
    async def identity_boundaries(request:Request,call_next):
        path=request.url.path
        flow_path=path in ('/api/v1/auth/login','/api/v1/auth/signup','/api/v1/auth/callback')
        token=None
        try:
            # Reject browser cross-origin access before any local-mode dependency override.
            if path.startswith('/api/v1/') and path!='/api/v1/auth/callback':allowed_origin(request)
            if flow_path:
                source=provider()
                store=identity_store()
                if path.endswith('/callback'):
                    request.scope['session']=await run_in_threadpool(store.consume_flow,request.cookies.get(FLOW_COOKIE))
                else:
                    token=store.create_flow();request.scope['session']={}
            response=await call_next(request)
            if flow_path:
                if token and request.session:
                    await run_in_threadpool(store.save_flow,token,request.session)
                    response.set_cookie(FLOW_COOKIE,token,max_age=600,httponly=True,samesite='lax',secure=source.config.secure,path='/api/v1/auth')
                else:response.delete_cookie(FLOW_COOKIE,path='/api/v1/auth',httponly=True,samesite='lax')
        except StorageError as error:
            response=JSONResponse(status_code=error.status,content={'code':error.code,'message':error.message,'field_errors':[]})
        if path.startswith('/api/v1/'):
            response.headers['Cache-Control']='no-store'
            response.headers['Referrer-Policy']='no-referrer'
        return response
