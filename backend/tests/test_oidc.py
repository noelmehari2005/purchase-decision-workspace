"""Signed protocol fixtures: Authlib must reject altered identity claims.

HTTP responses are mocked, but signature, nonce, audience, issuer and expiry
validation use the real Authlib OIDC implementation, not a fake login route.
"""
import base64
import json
import time
import unittest

import httpx
from starlette.requests import Request

try:
    import authlib
except ImportError:
    authlib=None


def encoded(data):return base64.urlsafe_b64encode(data).rstrip(b'=')


@unittest.skipUnless(authlib,'Install backend requirements to test real OIDC validation.')
class OidcProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from backend.app.auth_provider import Auth0Provider,AuthSettings
        self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        self.provider=Auth0Provider(AuthSettings('example.auth0.com','client','secret','machine','machine-secret'))
        stamp=int(time.time())
        self.claims={'iss':'https://example.auth0.com/','sub':'auth0|test','aud':'client','iat':stamp,'exp':stamp+300,
                     'auth_time':stamp,'nonce':'nonce-a','email':'test@example.com','email_verified':True}
        self.provider.client.client_kwargs['transport']=httpx.MockTransport(self.respond)
    def token(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        header=encoded(json.dumps({'alg':'RS256','kid':'test'}).encode())
        payload=encoded(json.dumps(self.claims).encode())
        signing=header+b'.'+payload
        return (signing+b'.'+encoded(self.key.sign(signing,padding.PKCS1v15(),hashes.SHA256()))).decode()
    def respond(self,request):
        root='https://example.auth0.com/'
        if request.url.path=='/.well-known/openid-configuration':
            return httpx.Response(200,json={'issuer':root,'authorization_endpoint':root+'authorize','token_endpoint':root+'oauth/token',
                'jwks_uri':root+'.well-known/jwks','id_token_signing_alg_values_supported':['RS256']})
        if request.url.path=='/oauth/token':
            return httpx.Response(200,json={'access_token':'test-access','token_type':'Bearer','id_token':self.token()})
        if request.url.path=='/.well-known/jwks':
            numbers=self.key.public_key().public_numbers()
            value=lambda number:encoded(number.to_bytes((number.bit_length()+7)//8,'big')).decode()
            return httpx.Response(200,json={'keys':[{'kty':'RSA','kid':'test','use':'sig','alg':'RS256','n':value(numbers.n),'e':value(numbers.e)}]})
        raise AssertionError('Unexpected provider endpoint')
    def request(self):
        return Request({'type':'http','method':'GET','path':'/api/v1/auth/callback','query_string':b'code=code-a&state=state-a',
            'headers':[],'session':{'_state_auth0_state-a':{'data':{'nonce':'nonce-a','code_verifier':'v'*64,
                'redirect_uri':'http://127.0.0.1:5173/api/v1/auth/callback'},'exp':time.time()+600}}})
    async def test_login_uses_browser_state_nonce_and_s256_pkce(self):
        import hashlib
        from urllib.parse import urlsplit,parse_qs
        request=self.request();request.scope['session']={}
        result=await self.provider.login(request)
        query=parse_qs(urlsplit(result.headers['location']).query)
        self.assertEqual(query['connection'],['Username-Password-Authentication'])
        self.assertEqual(query['prompt'],['login'])
        self.assertEqual(query['max_age'],['0'])
        self.assertEqual(query['code_challenge_method'],['S256'])
        state=request.session['_state_auth0_'+query['state'][0]]['data']
        self.assertEqual(query['code_challenge'][0],encoded(hashlib.sha256(state['code_verifier'].encode()).digest()).decode())
        self.assertEqual(query['nonce'][0],state['nonce'])

    async def test_valid_signed_identity(self):
        claims=await self.provider.claims(self.request())
        self.assertEqual(claims['sub'],'auth0|test')
    async def test_wrong_audience(self):
        self.claims['aud']='another-client'
        with self.assertRaises(Exception):await self.provider.claims(self.request())
    async def test_wrong_issuer(self):
        self.claims['iss']='https://evil.example/'
        with self.assertRaises(Exception):await self.provider.claims(self.request())
    async def test_wrong_nonce(self):
        self.claims['nonce']='wrong'
        with self.assertRaises(Exception):await self.provider.claims(self.request())
    async def test_expired_identity(self):
        self.claims['exp']=int(time.time())-100
        with self.assertRaises(Exception):await self.provider.claims(self.request())
    async def test_social_identity_is_not_accepted(self):
        self.claims['sub']='google-oauth2|test'
        with self.assertRaises(ValueError):await self.provider.claims(self.request())
    async def test_callback_without_matching_browser_state(self):
        request=self.request();request.scope['session']={}
        with self.assertRaises(Exception):await self.provider.claims(request)
    async def test_altered_signature(self):
        original=self.token
        self.token=lambda:original().rsplit('.',1)[0]+'.'+encoded(b'not-a-valid-signature').decode()
        with self.assertRaises(Exception):await self.provider.claims(self.request())
