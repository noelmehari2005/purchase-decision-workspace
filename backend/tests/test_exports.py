"""Export privacy, completeness, consistency and limits with no live providers."""
import json
import os
from unittest import TestCase, skipUnless
from unittest.mock import patch
from uuid import uuid4
from backend.app.exports import build_export
from backend.app.workspaces import StorageError, build_snapshot
from backend.tests.test_storage import MemoryRepository,state_fixture
from backend.tests import test_auth as auth_helpers

class ExportTests(TestCase):
    def setUp(self):
        self.repo=MemoryRepository();self.saved=self.repo.create('a',uuid4(),state_fixture())
        self.snapshot=self.repo.save_snapshot('a',build_snapshot(self.saved,uuid4()))
    def test_complete_saved_inputs_provenance_and_frozen_results_without_secrets(self):
        from backend.app.icecat import map_product
        from backend.tests.test_imports import sample
        state=state_fixture();e=map_product(sample(),{},uuid4()).model_dump(mode='json')
        state['records'][1]['draft']['evidence']=e
        state['records'][1]['draft']['cpu']='My correction'
        self.repo.update('a',self.saved['id'],1,state)
        self.repo.create('b',uuid4(),state_fixture())
        data=json.loads(build_export(self.repo,'a'))
        self.assertEqual(data['counts'],{'workspaces':1,'historical_reviews':1})
        self.assertEqual(data['workspaces'][0]['state']['plan'],state['plan'])
        self.assertEqual(data['workspaces'][0]['state']['records'][1]['draft']['evidence'],e)
        self.assertEqual(data['historical_reviews'][0]['evaluation'],self.snapshot['evaluation'])
        self.assertEqual(data['historical_reviews'][0]['state']['records'][1]['draft']['cpu'],'')
        raw=json.dumps(data)
        for key in ['owner_id','client_secret','app_sessions','csrf','api-token']:
            self.assertNotIn(key,raw)
    def test_empty_export_is_valid_and_does_not_create_records(self):
        data=json.loads(build_export(self.repo,'empty'))
        self.assertEqual(data['counts'],{'workspaces':0,'historical_reviews':0})
        self.assertEqual(len(self.repo.decisions),1)
    def test_no_truncation_for_record_or_byte_limits(self):
        for name,limit in [('MAX_WORKSPACES',0),('MAX_REVIEWS',0),('MAX_EXPORT_BYTES',100)]:
            with self.subTest(name=name),patch('backend.app.exports.'+name,limit):
                with self.assertRaises(StorageError) as raised:build_export(self.repo,'a')
                self.assertEqual(raised.exception.status,413)
    def test_concurrent_updates_and_newer_reviews_require_retry(self):
        with patch.object(self.repo,'export_revisions',return_value={}):
            with self.assertRaises(StorageError) as raised:build_export(self.repo,'a')
            self.assertEqual(raised.exception.code,'export_changed')
        key=next(iter(self.repo.snapshots));self.repo.snapshots[key]['decision_revision']=2
        with self.assertRaises(StorageError):build_export(self.repo,'a')
    def test_only_allowlisted_fields_are_exported(self):
        key=next(iter(self.repo.decisions));self.repo.decisions[key]['server_secret']='hidden'
        key=next(iter(self.repo.snapshots));self.repo.snapshots[key]['server_secret']='hidden'
        self.assertNotIn(b'hidden',build_export(self.repo,'a'))
    def test_incomplete_unconfirmed_drafts_can_export(self):
        state=state_fixture();state['records'][1]['confirmed']=None;state['records'][1]['revision']=0
        state['records'][1]['draft']['price']='unfinished'
        self.repo.create('unfinished',uuid4(),state)
        data=json.loads(build_export(self.repo,'unfinished'))
        self.assertEqual(data['workspaces'][0]['state']['records'][1]['draft']['price'],'unfinished')

class ExportAuthTests(TestCase):
    setUp=auth_helpers.AuthApiTests.setUp
    tearDown=auth_helpers.AuthApiTests.tearDown
    authenticate=auth_helpers.AuthApiTests.authenticate
    create=auth_helpers.AuthApiTests.create
    def test_export_is_private_attachment_and_never_cached(self):
        saved=self.create()
        result=self.client.get('/api/v1/account/export')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['workspaces'][0]['id'],saved['id'])
        self.assertIn('attachment',result.headers['content-disposition'])
        self.assertEqual(result.headers['cache-control'],'no-store')
        self.assertEqual(result.headers['x-content-type-options'],'nosniff')
        self.authenticate('b')
        self.assertEqual(self.client.get('/api/v1/account/export').json()['counts']['workspaces'],0)
    def test_missing_unverified_cross_origin_and_restricted_accounts_are_denied(self):
        self.assertEqual(self.client.get('/api/v1/account/export').status_code,401)
        self.authenticate('unverified');self.assertEqual(self.client.get('/api/v1/account/export').status_code,403)
        self.authenticate();self.assertEqual(self.client.get('/api/v1/account/export',headers={'Origin':'https://evil.example'}).status_code,403)
        self.store.session.side_effect=StorageError(403,'account_restricted','Account unavailable')
        self.assertEqual(self.client.get('/api/v1/account/export').status_code,403)

@skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI for real Mongo export tests.')
class MongoExportTests(TestCase):
    def setUp(self):
        from pymongo import MongoClient
        from backend.app.repositories import MongoRepository
        self.client=MongoClient(os.environ['PDW_TEST_MONGO_URI'],serverSelectionTimeoutMS=2000,tz_aware=True)
        self.db='pdw_test_'+uuid4().hex;self.repo=MongoRepository(self.client[self.db])
    def tearDown(self):self.client.drop_database(self.db);self.client.close()
    def test_all_saved_pages_and_history_are_owned_and_revisions_are_preserved(self):
        for _ in range(12):
            saved=self.repo.create('a',uuid4(),state_fixture());self.repo.save_snapshot('a',build_snapshot(saved,uuid4()))
        self.repo.create('b',uuid4(),state_fixture())
        data=json.loads(build_export(self.repo,'a'))
        self.assertEqual(data['counts'],{'workspaces':12,'historical_reviews':12})
        self.assertEqual(len(json.loads(build_export(self.repo,'b'))['workspaces']),1)
        self.assertNotIn('owner_id',json.dumps(data))
        self.assertEqual(len(self.repo.export_revisions('a',100)),12)
