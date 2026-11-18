"""Validate both API authorization and the original signed authentication time.

Only this bootstrap consumes provider tokens. Subsequent requests use a short
opaque application session kept in browser memory and hashed in MongoDB.
"""
import math
import time
from functools import lru_cache
from threading import Lock

import httpx
from joserfc import jwt,jwk

from .workspaces import StorageError


class SpaVerifier:
    def __init__(self,issuer,client,audience):
        self.issuer,self.client,self.audience=issuer,client,audience
        self._keys=None
        self._until=0
        self._lock=Lock()

    def keys(self):
        with self._lock:
            if self._keys is not None and time.monotonic()<self._until:
                return self._keys
            try:
                # Fixed configured issuer only; never follow a JWT-supplied key URL.
                with httpx.Client(timeout=6,follow_redirects=False) as client:
                    response=client.get(self.issuer+'.well-known/jwks.json')
                    response.raise_for_status()
                    if len(response.content)>100_000:raise ValueError('Oversized key set')
                    values=response.json()['keys']
                    values=[key for key in values if key.get('kty')=='RSA' and key.get('use','sig')=='sig' and key.get('alg','RS256')=='RS256']
                    self._keys=jwk.KeySet.import_key_set({'keys':values})
                    self._until=time.monotonic()+300
                    return self._keys
            except Exception as error:
                raise StorageError(503,'identity_unavailable','Cannot verify sign-in right now. Please try again.') from error

    def decode(self,value,audience,keys):
        if not isinstance(value,str) or not 0<len(value)<=16_384:raise ValueError('Invalid token')
        token=jwt.decode(value,keys,algorithms=['RS256'])
        if any(name in token.header for name in ('jku','jwk','x5u')):raise ValueError('Embedded keys forbidden')
        jwt.JWTClaimsRegistry(leeway=30,iss={'essential':True,'value':self.issuer},
            aud={'essential':True,'value':audience},exp={'essential':True},
            iat={'essential':True},sub={'essential':True}).validate(token.claims)
        for name in ('iat','exp'):
            if type(token.claims[name]) not in (int,float) or not math.isfinite(token.claims[name]):raise ValueError('Invalid timestamp')
        if token.claims['iat']>time.time()+30:raise ValueError('Future token')
        return token.claims

    def verify(self,access_token,id_token):
        keys=self.keys()
        try:
            access=self.decode(access_token,self.audience,keys)
            identity=self.decode(id_token,self.client,keys)
            subject=identity['sub']
            if (not isinstance(subject,str) or not subject.startswith('auth0|') or len(subject)>256
                    or access['sub']!=subject or access.get('azp')!=self.client):
                raise ValueError('Wrong identity or authorized party')
            if identity.get('azp',self.client)!=self.client:raise ValueError('Wrong identity client')
            stamp=identity.get('auth_time')
            if type(stamp) not in (float,int) or not math.isfinite(stamp) or not time.time()-600<=stamp<=time.time()+30:
                raise ValueError('Fresh authentication required')
            return subject,stamp
        except Exception as error:
            raise StorageError(401,'signin_invalid','Sign-in could not be verified. Please sign in again.') from error


@lru_cache(maxsize=1)
def verifier(issuer,client,audience):
    return SpaVerifier(issuer,client,audience)
