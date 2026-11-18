"""Signed staging tokens; all provider/database traffic is controlled."""
import copy
import os
import time
import unittest
from unittest.mock import patch,MagicMock
from starlette.requests import Request
from joserfc import jwt,jwk
from backend.app.spa_auth import SpaVerifier
from backend.app.runtime import runtime,session_token,check_tester
from backend.app.workspaces import StorageError

STAGING={'PDW_RUNTIME':'staging','PDW_APP_ORIGIN':'https://owner.github.io',
    'PDW_API_ORIGIN':'https://pdw-test.onrender.com','PDW_AUTH0_SPA_CLIENT_ID':'spa',
    'PDW_AUTH0_API_AUDIENCE':'https://pdw-api','PDW_TESTER_EMAILS':'test@example.com',
    'PDW_MONGO_URI':'mongodb+srv://user:placeholder@cluster.example.net/', 'PDW_MONGO_DATABASE':'pdw_staging',
    'PDW_AUTH_MODE':'auth0','PDW_LOCAL_STORAGE':'0'}


class StagingBoundaryTests(unittest.TestCase):
    def test_render_assigned_origin_is_validated_and_explicit_origin_takes_precedence(self):
        env={**STAGING,'RENDER_EXTERNAL_URL':'https://assigned.onrender.com'}
        env.pop('PDW_API_ORIGIN')
        self.assertEqual(runtime(env).api_host,'assigned.onrender.com')
        env['PDW_API_ORIGIN']='https://explicit.example.com'
        self.assertEqual(runtime(env).api_host,'explicit.example.com')
        env['PDW_API_ORIGIN']='http://invalid.example.com'
        with self.assertRaises(ValueError):runtime(env)
        env.pop('PDW_API_ORIGIN');env['RENDER_EXTERNAL_URL']='https://assigned.onrender.com/path'
        with self.assertRaises(ValueError):runtime(env)

    def test_exact_https_origins_and_no_local_demo_fallback(self):
        with patch.dict(os.environ,STAGING):
            self.assertTrue(runtime().hosted)
            for key,value in [('PDW_APP_ORIGIN','https://owner.github.io/repo/'),('PDW_API_ORIGIN','http://localhost:8000'),
                    ('PDW_RUNTIME','production'),('PDW_AUTH_MODE','local'),('PDW_LOCAL_STORAGE','1'),
                    ('PDW_TESTER_EMAILS',''),('PDW_MONGO_URI','mongodb://localhost:27017')]:
                with self.subTest(key=key,value=value),patch.dict(os.environ,{key:value}):
                    with self.assertRaises(ValueError):runtime()

    def test_cookie_is_ignored_and_verified_tester_is_required(self):
        with patch.dict(os.environ,STAGING):
            request=Request({'type':'http','headers':[(b'cookie',b'pdw_session=cookie')]})
            self.assertIsNone(session_token(request))
            request=Request({'type':'http','headers':[(b'authorization',b'Bearer opaque-session')]})
            self.assertEqual(session_token(request),'opaque-session')
            check_tester({'email':'TEST@example.com','email_verified':True})
            for user in ({'email':'other@example.com','email_verified':True},{'email':'test@example.com','email_verified':False}):
                with self.assertRaises(StorageError):check_tester(user)

    def test_readiness_recognizes_public_spa_config_without_a_web_client_secret(self):
        from backend.app.readiness import configuration_report
        env={**STAGING,'PDW_AUTH0_DOMAIN':'example.auth0.com','PDW_AUTH0_MANAGEMENT_CLIENT_ID':'reader',
             'PDW_AUTH0_MANAGEMENT_CLIENT_SECRET':'private-placeholder'}
        checks={item['check']:item['status'] for item in configuration_report(env)['checks']}
        self.assertEqual(checks['email_password_auth'],'configured_unverified')
        self.assertEqual(checks['private_storage'],'configured_unverified')
        self.assertNotIn('private-placeholder',str(configuration_report(env)))


class SpaSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=jwk.RSAKey.generate_key(2048,parameters={'kid':'fixture'})
        cls.keys=jwk.KeySet.import_key_set({'keys':[cls.key.as_dict(private=False)]})

    def setUp(self):
        self.verifier=SpaVerifier('https://example.auth0.com/','spa','https://pdw-api')
        self.verifier.keys=MagicMock(return_value=self.keys)
        now=int(time.time())
        self.identity={'iss':'https://example.auth0.com/','aud':'spa','sub':'auth0|test','exp':now+300,'iat':now,'auth_time':now}
        self.access={**self.identity,'aud':'https://pdw-api','azp':'spa'}

    def sign(self,claims,key=None):
        return jwt.encode({'alg':'RS256','kid':'fixture'},claims,key or self.key)

    def verify(self):return self.verifier.verify(self.sign(self.access),self.sign(self.identity))

    def test_valid_tokens_preserve_original_authentication_time(self):
        self.identity['auth_time']-=120
        self.assertEqual(self.verify(),('auth0|test',self.identity['auth_time']))

    def test_invalid_claims_and_refresh_do_not_fabricate_fresh_signin(self):
        for target,field,value in [('access','iss','https://evil.example/'),('access','aud','spa'),('access','azp','other'),
                ('access','sub','auth0|other'),('identity','aud','other'),('identity','sub','google-oauth2|test'),
                ('identity','exp',0),('access','exp',0),('identity','auth_time',None),
                ('identity','auth_time',time.time()-700),('identity','auth_time',time.time()+100),
                ('identity','auth_time',float('nan')),('identity','iat',time.time()+100)]:
            original=copy.deepcopy(getattr(self,target))
            with self.subTest(target=target,field=field,value=value):
                getattr(self,target)[field]=value
                with self.assertRaises(StorageError):self.verify()
            setattr(self,target,original)

    def test_altered_signature_unsigned_and_wrong_algorithm(self):
        other=jwk.RSAKey.generate_key(2048,parameters={'kid':'fixture'})
        with self.assertRaises(StorageError):self.verifier.verify(self.sign(self.access,other),self.sign(self.identity))
        for invalid in ('bad','e30.e30.',self.sign(self.identity)):
            with self.assertRaises(StorageError):self.verifier.verify(invalid,self.sign(self.identity))
        symmetric=jwt.encode({'alg':'HS256'},self.access,jwk.OctKey.generate_key(256))
        with self.assertRaises(StorageError):self.verifier.verify(symmetric,self.sign(self.identity))

    def test_key_outage_is_not_invalid_credentials(self):
        self.verifier.keys=MagicMock(side_effect=StorageError(503,'identity_unavailable','Unavailable'))
        with self.assertRaises(StorageError) as raised:self.verify()
        self.assertEqual(raised.exception.status,503)


class StagingApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from starlette.middleware.cors import CORSMiddleware
        from backend.app import auth_api
        from backend.app.auth_provider import AuthSettings
        self.env=patch.dict(os.environ,STAGING);self.env.start();self.addCleanup(self.env.stop)
        self.store=MagicMock();self.store.create_session.return_value='opaque-session'
        self.source=MagicMock();self.source.config=AuthSettings('example.auth0.com','spa','unused','reader','secret')
        self.source.profile.return_value={'user_id':'auth0|test','email':'test@example.com','email_verified':True}
        self.verifier=MagicMock();self.verifier.verify.return_value=('auth0|test',int(time.time()))
        for target,value in [('backend.app.auth_api.provider',self.source),('backend.app.auth_api.identity_store',self.store),
                             ('backend.app.spa_auth.verifier',self.verifier)]:
            item=patch(target,return_value=value);item.start();self.addCleanup(item.stop)
        app=FastAPI();auth_api.install_auth(app)
        app.add_middleware(CORSMiddleware,allow_origins=[STAGING['PDW_APP_ORIGIN']],allow_credentials=False,
            allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Authorization','Content-Type','X-PDW-CSRF'])
        self.web=TestClient(app);self.addCleanup(self.web.close)
        self.headers={'Origin':STAGING['PDW_APP_ORIGIN'],'Authorization':'Bearer signed-access'}

    def test_bootstrap_returns_only_opaque_session_without_cookie(self):
        result=self.web.post('/api/v1/auth/spa-session',headers=self.headers,json={'id_token':'signed-id'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json(),{'session_token':'opaque-session'})
        self.assertNotIn('set-cookie',result.headers)
        self.assertEqual(result.headers['cache-control'],'no-store')
        self.assertEqual(result.headers['access-control-allow-origin'],STAGING['PDW_APP_ORIGIN'])
        self.assertNotIn('access-control-allow-credentials',result.headers)
        self.verifier.verify.assert_called_once_with('signed-access','signed-id')

    def test_database_failure_logs_stage_and_numeric_code_without_credentials(self):
        from pymongo.errors import OperationFailure
        private='mongodb+srv://private-user:private-password@host/ signed-access signed-id'
        self.store.create_session.side_effect=OperationFailure(private,code=18)
        with self.assertLogs('pdw.auth',level='WARNING') as captured:
            result=self.web.post('/api/v1/auth/spa-session',headers=self.headers,json={'id_token':'signed-id'})
        self.assertEqual(result.status_code,503)
        output=' '.join(captured.output)+result.text
        self.assertIn('stage=application_session',output)
        self.assertIn('database_code=18',output)
        for value in ('private-user','private-password','signed-access','signed-id'):
            self.assertNotIn(value,output)

    def test_wrapped_storage_and_provider_failures_keep_distinct_redacted_stages(self):
        import httpx
        from backend.app import auth_api
        from pymongo.errors import OperationFailure
        database_error=StorageError(503,'identity_unavailable','Cannot reach account storage.')
        database_error.__cause__=OperationFailure('private-database-password',code=18)
        with patch.object(auth_api,'identity_store',side_effect=database_error),self.assertLogs('pdw.auth',level='WARNING') as captured:
            result=self.web.post('/api/v1/auth/spa-session',headers=self.headers,json={'id_token':'signed-id'})
        self.assertEqual(result.status_code,503)
        self.assertIn('stage=account_storage',' '.join(captured.output))
        self.assertIn('database_code=18',' '.join(captured.output))
        self.assertNotIn('private-database-password',' '.join(captured.output)+result.text)
        request=httpx.Request('GET','https://example.auth0.com/api/v2/users/test')
        error=StorageError(503,'identity_unavailable','Unable to verify your account.')
        error.__cause__=httpx.HTTPStatusError('private-provider-secret',request=request,response=httpx.Response(401,request=request))
        self.source.profile.side_effect=error
        with self.assertLogs('pdw.auth',level='WARNING') as captured:
            result=self.web.post('/api/v1/auth/spa-session',headers=self.headers,json={'id_token':'signed-id'})
        self.assertEqual(result.status_code,503)
        self.assertIn('stage=account_profile',' '.join(captured.output))
        self.assertIn('provider_status=401',' '.join(captured.output))
        self.assertNotIn('private-provider-secret',' '.join(captured.output)+result.text)

    def test_unknown_tester_and_blocked_profile_cannot_create_session(self):
        for profile in ({'email':'other@example.com','email_verified':True},{'email':'test@example.com','email_verified':False},
                        {'email':'test@example.com','email_verified':True,'blocked':True}):
            self.source.profile.return_value={'user_id':'auth0|test',**profile}
            result=self.web.post('/api/v1/auth/spa-session',headers=self.headers,json={'id_token':'signed-id'})
            self.assertEqual(result.status_code,403,result.text)
        self.store.create_session.assert_not_called()

    def test_origin_denial_before_provider_and_old_cookie_flow_disabled(self):
        for origin in ('https://evil.example','null',''):
            result=self.web.post('/api/v1/auth/spa-session',headers={**self.headers,'Origin':origin},json={'id_token':'signed-id'})
            self.assertEqual(result.status_code,403)
        self.source.profile.assert_not_called();self.store.create_session.assert_not_called()
        self.assertEqual(self.web.get('/api/v1/auth/login').status_code,404)
        self.assertEqual(self.web.get('/api/v1/auth/callback').status_code,404)
        self.assertEqual(self.web.get('/api/v1/auth/session',headers={'Cookie':'pdw_session=old'}).json()['authenticated'],False)
        preflight=self.web.options('/api/v1/auth/spa-session',headers={'Origin':STAGING['PDW_APP_ORIGIN'],
            'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
        self.assertEqual(preflight.status_code,200)
