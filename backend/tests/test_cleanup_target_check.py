import unittest
from unittest.mock import MagicMock,patch
import os
import httpx
from types import SimpleNamespace
from backend.app import cleanup_target_check as checks
from backend.app.cleanup_target_check import inspect_target


class CleanupTargetTests(unittest.TestCase):
    def fixture(self):
        source=MagicMock();source.config=SimpleNamespace(issuer='https://example.auth0.com/',client_id='web',management_id='reader')
        source.profile.return_value={'user_id':'auth0|disposable','email':'test+pdw-cleanup@example.com'}
        database=MagicMock()
        collections={name:MagicMock() for name in ('users','decisions','snapshots','import_receipts','app_sessions','deletion_ledger')}
        database.__getitem__.side_effect=collections.__getitem__
        for collection in collections.values():collection.find_one.return_value=None
        return source,database

    def test_empty_app_database_and_matching_profile_pass_without_any_writes(self):
        source,database=self.fixture()
        ok,_=inspect_target('auth0|disposable','test+pdw-cleanup@example.com',source,database)
        self.assertTrue(ok)
        database.command.assert_called_once_with('ping')
        for name in ('users','decisions','snapshots','import_receipts','app_sessions','deletion_ledger'):
            calls=database[name].method_calls
            self.assertEqual([call[0] for call in calls],['find_one'])
        source.profile.assert_called_once_with('auth0|disposable')

    def test_wrong_profile_or_any_application_record_rejects_target(self):
        for key,value in [('user_id','auth0|other'),('email','other@example.com')]:
            source,database=self.fixture();source.profile.return_value[key]=value
            self.assertFalse(inspect_target('auth0|disposable','test+pdw-cleanup@example.com',source,database)[0])
            database.command.assert_not_called()
        for name in ('users','decisions','snapshots','import_receipts','app_sessions','deletion_ledger'):
            with self.subTest(collection=name):
                source,database=self.fixture();database[name].find_one.return_value={'_id':'existing'}
                self.assertFalse(inspect_target('auth0|disposable','test+pdw-cleanup@example.com',source,database)[0])

    def test_unavailable_database_cannot_be_treated_as_empty(self):
        source,database=self.fixture();database.command.side_effect=RuntimeError('offline')
        with self.assertRaises(RuntimeError):inspect_target('auth0|disposable','test+pdw-cleanup@example.com',source,database)

    def test_explicit_deletion_repeats_preflight_and_targets_only_the_verified_user(self):
        source,database=self.fixture()
        with patch.dict(os.environ,{'PDW_AUTH0_DELETION_CLIENT_ID':'cleanup'}),patch.object(checks,'delete_identity') as delete,patch.object(checks,'verify_missing',return_value=True) as verify:
            ok,_=checks.run_check('auth0|disposable','test+pdw-cleanup@example.com',source,database,'auth0|disposable')
            self.assertTrue(ok)
            source.profile.assert_called_once_with('auth0|disposable')
            delete.assert_called_once_with('auth0|disposable')
            verify.assert_called_once_with('auth0|disposable',source)
            for name in ('users','decisions','snapshots','import_receipts','app_sessions','deletion_ledger'):
                self.assertEqual([call[0] for call in database[name].method_calls],['find_one'])

    def test_read_only_mismatched_confirmation_or_new_app_records_never_delete(self):
        for confirmation,has_user in [(None,False),('auth0|wrong',False),('auth0|disposable',True)]:
            source,database=self.fixture()
            if has_user:database['users'].find_one.return_value={'_id':'now-registered'}
            with self.subTest(confirmation=confirmation,has_user=has_user),patch.object(checks,'delete_identity') as delete:
                checks.run_check('auth0|disposable','test+pdw-cleanup@example.com',source,database,confirmation)
                delete.assert_not_called()

    def test_verification_requires_404_and_does_not_treat_provider_outage_as_absence(self):
        source,_=self.fixture();source._token.return_value='private-token'
        for status in (404,200,503):
            calls=[]
            def handler(request):
                calls.append(request)
                return httpx.Response(status)
            original=httpx.Client
            def client(**kwargs):return original(transport=httpx.MockTransport(handler),**kwargs)
            with self.subTest(status=status),patch.object(checks.httpx,'Client',side_effect=client):
                if status==503:
                    with self.assertRaises(httpx.HTTPStatusError):checks.verify_missing('auth0|disposable',source)
                else:self.assertEqual(checks.verify_missing('auth0|disposable',source),status==404)
            self.assertEqual(len(calls),1);self.assertEqual(calls[0].method,'GET')
            self.assertIn('auth0%7Cdisposable',str(calls[0].url))
            self.assertNotIn('private-token',str(calls[0].url))
