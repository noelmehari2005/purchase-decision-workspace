"""Cleanup credential checks must never call a user or deletion endpoint."""
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import httpx
from backend.app import cleanup_check
from backend.app.auth_provider import AuthSettings


class CleanupAccessTests(unittest.TestCase):
    def test_only_token_endpoint_is_used_and_scope_must_be_confirmed(self):
        config=AuthSettings('example.auth0.com','web','fake','reader','fake')
        for scope,expected in [('delete:users',True),('',False),('read:users',False),('delete:users read:users',False)]:
            calls=[]
            def handler(request):
                calls.append((request.method,request.url.path))
                self.assertEqual(calls,[('POST','/oauth/token')])
                return httpx.Response(200,json={'access_token':'private-fake-token','scope':scope})
            original=httpx.Client
            def client(**kwargs):return original(transport=httpx.MockTransport(handler),**kwargs)
            with self.subTest(scope=scope),patch.dict(os.environ,{'PDW_AUTH0_DELETION_CLIENT_ID':'cleanup','PDW_AUTH0_DELETION_CLIENT_SECRET':'fake-secret'}), \
                    patch.object(cleanup_check,'settings',return_value=config),patch.object(cleanup_check.httpx,'Client',side_effect=client):
                ok,message=cleanup_check.check_access()
                self.assertEqual(ok,expected)
                self.assertNotIn('private-fake-token',message)
                self.assertNotIn('fake-secret',message)

    def test_shared_client_is_rejected_before_network_and_error_details_are_redacted(self):
        config=AuthSettings('example.auth0.com','web','fake','reader','fake')
        with patch.dict(os.environ,{'PDW_AUTH0_DELETION_CLIENT_ID':'reader','PDW_AUTH0_DELETION_CLIENT_SECRET':'fake-secret'}), \
                patch.object(cleanup_check,'settings',return_value=config),patch.object(cleanup_check.httpx,'Client') as client:
            self.assertFalse(cleanup_check.check_access()[0]);client.assert_not_called()
        request=httpx.Request('POST','https://example.auth0.com/oauth/token')
        response=httpx.Response(403,request=request)
        error=httpx.HTTPStatusError('private-token private-secret',request=request,response=response)
        with patch.object(cleanup_check,'check_access',side_effect=error),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cleanup_check.main(),1)
            self.assertIn('HTTP 403',output.getvalue())
            self.assertNotIn('private-',output.getvalue())
