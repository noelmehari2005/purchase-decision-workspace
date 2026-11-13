"""Provider wire contracts without real accounts, secrets, or network traffic."""
import json
import unittest
from unittest.mock import patch

import httpx
from backend.app.auth_provider import Auth0Provider,AuthSettings
from backend.app.workspaces import StorageError


class ProviderRequestTests(unittest.TestCase):
    def setUp(self):
        self.config=AuthSettings('example.auth0.com','client','fake-secret','machine','fake-machine-secret')
        self.source=Auth0Provider(self.config)
        self.original_client=httpx.Client
        self.calls=[]
    def handler(self,request):
        self.calls.append(request)
        if request.url.path=='/oauth/token':
            body=json.loads(request.content)
            self.assertEqual(body['scope'],'read:users')
            self.assertEqual(body['audience'],'https://example.auth0.com/api/v2/')
            return httpx.Response(200,json={'access_token':'fake-token','expires_in':3600})
        if request.url.path=='/api/v2/users/auth0|example':
            if 'fields' in request.url.params:
                return httpx.Response(400,json={'errorCode':'invalid_query_string'})
            self.assertEqual(request.headers['Authorization'],'Bearer fake-token')
            return httpx.Response(200,json={'user_id':'auth0|example','email':'example@example.com','email_verified':True,
                'blocked':False,'last_password_reset':'2026-11-13T07:00:00.010Z','user_metadata':{'private_extra':'discard'},
                'identities':[{'provider':'auth0'}]})
        raise AssertionError('Unexpected endpoint')
    def factory(self,**kwargs):return self.original_client(transport=httpx.MockTransport(self.handler),**kwargs)
    def test_basic_user_request_keeps_password_version_without_rejected_field_query(self):
        with patch('backend.app.auth_provider.httpx.Client',side_effect=self.factory):
            profile=self.source.profile('auth0|example')
        self.assertEqual(set(profile),{'user_id','email','email_verified','blocked','last_password_reset'})
        self.assertEqual(profile['last_password_reset'],'2026-11-13T07:00:00.010Z')
        self.assertNotIn('user_metadata',profile)
        self.assertEqual(len(self.calls),2)
    def test_management_token_is_reused_without_new_credential_exchange(self):
        with patch('backend.app.auth_provider.httpx.Client',side_effect=self.factory):
            self.source.profile('auth0|example');self.source.profile('auth0|example')
        self.assertEqual(sum(request.url.path=='/oauth/token' for request in self.calls),1)
    def test_provider_errors_do_not_echo_raw_response_or_credentials(self):
        def fail(request):return httpx.Response(400,json={'message':'fake-machine-secret private profile data'})
        def factory(**kwargs):return self.original_client(transport=httpx.MockTransport(fail),**kwargs)
        with patch('backend.app.auth_provider.httpx.Client',side_effect=factory),self.assertRaises(StorageError) as raised:
            self.source.profile('auth0|example')
        self.assertNotIn('fake-machine-secret',raised.exception.message)
        self.assertNotIn('private profile data',raised.exception.message)
