"""Auth0 configuration and protocol adapter; secrets and tokens stay server-side."""
from dataclasses import dataclass,field
from functools import lru_cache
import os
import re
import time
from urllib.parse import quote
from threading import Lock

import httpx
from .workspaces import StorageError


@dataclass(frozen=True)
class AuthSettings:
    domain:str
    client_id:str
    client_secret:str=field(repr=False)
    management_id:str
    management_secret:str=field(repr=False)
    connection:str='Username-Password-Authentication'
    origin:str='http://127.0.0.1:5173'

    @property
    def issuer(self):return 'https://'+self.domain+'/'
    @property
    def secure(self):return self.origin.startswith('https://')


def auth_mode():
    mode=os.environ.get('PDW_AUTH_MODE','auth0')
    if mode not in ('auth0','local'):
        raise StorageError(503,'auth_unavailable','Check the account setup before enabling saved workspaces.')
    return mode


def settings():
    domain=os.environ.get('PDW_AUTH0_DOMAIN','').strip()
    origin=os.environ.get('PDW_APP_ORIGIN','http://127.0.0.1:5173').rstrip('/')
    # This milestone deliberately supports local development, with a fixed provider destination.
    if origin not in ('http://127.0.0.1:5173','http://localhost:5173') or not re.fullmatch(r'[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.auth0\.com',domain):
        raise StorageError(503,'auth_unconfigured','Email/password sign-in is waiting for local Auth0 setup.')
    values=[os.environ.get(k,'').strip() for k in ('PDW_AUTH0_CLIENT_ID','PDW_AUTH0_CLIENT_SECRET',
        'PDW_AUTH0_MANAGEMENT_CLIENT_ID','PDW_AUTH0_MANAGEMENT_CLIENT_SECRET')]
    if not all(values):
        raise StorageError(503,'auth_unconfigured','Email/password sign-in is waiting for local Auth0 setup.')
    return AuthSettings(domain,*values,connection=os.environ.get('PDW_AUTH0_CONNECTION','Username-Password-Authentication'),origin=origin)


class Auth0Provider:
    def __init__(self,config):
        from authlib.integrations.starlette_client import OAuth
        self.config=config
        oauth=OAuth()
        oauth.register('auth0',client_id=config.client_id,client_secret=config.client_secret,
            server_metadata_url=config.issuer+'.well-known/openid-configuration',
            client_kwargs={'scope':'openid email profile','code_challenge_method':'S256','timeout':8.0})
        self.client=oauth.create_client('auth0')
        self._management_token=None
        self._management_until=0
        self._lock=Lock()

    async def login(self,request,signup=False):
        options={'connection':self.config.connection,'prompt':'login','max_age':0}
        if signup:options['screen_hint']='signup'
        return await self.client.authorize_redirect(request,self.config.origin+'/api/v1/auth/callback',**options)

    async def claims(self,request):
        token=await self.client.authorize_access_token(request,claims_options={
            'iss':{'essential':True,'value':self.config.issuer},
            'auth_time':{'essential':True}},leeway=30)
        claims=token.get('userinfo')
        if not claims or claims.get('iss')!=self.config.issuer or not str(claims.get('sub','')).startswith('auth0|'):
            raise ValueError('Unsupported identity')
        authenticated=claims.get('auth_time')
        if type(authenticated) not in (float,int) or not time.time()-600<=authenticated<=time.time()+30:
            raise ValueError('Fresh authentication required')
        return claims

    def _token(self):
        with self._lock:
            if self._management_token and time.time()<self._management_until:return self._management_token
            with httpx.Client(timeout=6.0) as client:
                response=client.post(self.config.issuer+'oauth/token',json={'grant_type':'client_credentials',
                    'client_id':self.config.management_id,'client_secret':self.config.management_secret,
                    'audience':self.config.issuer+'api/v2/','scope':'read:users'})
                response.raise_for_status(); body=response.json()
            self._management_token=body['access_token']
            self._management_until=time.time()+max(0,min(int(body.get('expires_in',0)),3600)-30)
            return self._management_token

    def profile(self,subject):
        try:
            with httpx.Client(timeout=6.0) as client:
                response=client.get(self.config.issuer+'api/v2/users/'+quote(subject,safe=''),
                    headers={'Authorization':'Bearer '+self._token()})
                response.raise_for_status()
                body=response.json()
                # Some tenants reject last_password_reset in the fields query.
                # The basic documented GET includes it; discard all unrelated data
                # immediately instead of logging, storing, or returning a raw profile.
                return {key:body.get(key) for key in ('user_id','email','email_verified','blocked','last_password_reset')}
        except Exception as error:
            raise StorageError(503,'identity_unavailable','Unable to verify your account right now. Your saved records are unchanged.') from error

    def request_reset(self,email):
        with httpx.Client(timeout=6.0) as client:
            client.post(self.config.issuer+'dbconnections/change_password',json={'client_id':self.config.client_id,
                'email':email,'connection':self.config.connection})


@lru_cache(maxsize=1)
def configured_provider(config):
    return Auth0Provider(config)


def provider():
    config=settings()
    try:return configured_provider(config)
    except ImportError as error:
        raise StorageError(503,'auth_dependencies_missing','Install the current backend requirements and restart the backend to enable sign-in.') from error
