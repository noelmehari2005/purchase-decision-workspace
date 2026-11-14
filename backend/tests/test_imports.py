"""Import contract, normalization, bounded HTTP, and private-preview regressions."""
import os
from copy import deepcopy
from uuid import uuid4
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app import import_api
from backend.app.import_models import ImportRequest
from backend.app.icecat import identify, map_product, fetch_product, MAX_BYTES
from backend.app.storage_api import repository
from backend.app.repositories import MongoRepository
from backend.app.workspaces import StorageError


def sample():
    # Deliberately synthetic selected fields, shaped by the official JSON manual.
    def f(fid, raw, unit=''):
        return {'RawValue':raw,'PresentationValue':str(raw),'Feature':{'ID':fid,'Measure':{'Sign':'','Signs':{'_':unit,'Language':'EN'}}}}
    return {'msg':'OK','data':{'GeneralInfo':{'IcecatId':123,'Brand':'Example','BrandPartCode':'ABC#US',
        'Title':'Example laptop','Category':{'CategoryID':'151'}},'FeaturesGroups':[{'Features':[
            f('47','CPU Model'),f('11381','16','GB'),f('1452','64','GB'),f('3318','1','TB'),
            f('94','1.45','kg'),f('8519','56','Wh'),f('944','14 inch'),f('1585','1920 x 1200')]}]}}

class MappingTests(unittest.TestCase):
    def test_exact_identifiers_and_no_arbitrary_fetch_destinations(self):
        for url in ['https://icecat.biz/en/p/brand/part/laptop-123.html#Specs', 'https://icecat.biz/en/p.cgi?product_id=123']:
            self.assertEqual(identify(ImportRequest(request_id=uuid4(),mode='link',value=url)),{'icecat_id':'123'})
        for url in ['http://icecat.biz/en/p/x-123.html','https://icecat.biz.evil.test/p/x-123.html',
                    'https://user:pass@icecat.biz/en/p/x-123.html','https://127.0.0.1/','file:///etc/passwd',
                    'https://icecat.biz:444/en/p/x-123.html','https://example.com/laptop']:
            with self.assertRaises(StorageError):identify(ImportRequest(request_id=uuid4(),mode='link',value=url))
        q=identify(ImportRequest(request_id=uuid4(),mode='mpn',brand='Example',mpn='ABC#US'))
        self.assertEqual(q['ProductCode'],'ABC#US')
    def test_installed_and_max_ram_capacity_and_runtime_remain_distinct(self):
        e=map_product(sample(),{'icecat_id':'123'},uuid4())
        values={f.field:f.normalized for f in e.fields}
        self.assertEqual({k:values[k] for k in ['ram','maxRam','storage','weight','batteryWh']},
                         {'ram':'16','maxRam':'64','storage':'1000','weight':'1450','batteryWh':'56'})
        self.assertNotIn('battery',values);self.assertNotIn('price',values);self.assertNotIn('os',values)
        self.assertIsNone(e.source_updated_at)
        self.assertEqual(e.source_url,'https://icecat.biz/en/search?keyword=ABC%23US')
        link='https://icecat.biz/en/p/example/abc/laptop-123.html?tracking=secret#Specs'
        self.assertEqual(map_product(sample(),{},uuid4(),link).source_url,link.split('?')[0])
    def test_mismatches_non_laptops_missing_identity_and_duplicate_specs(self):
        for identifier in [{'icecat_id':'124'},{'Brand':'Example','ProductCode':'ABC'}]:
            with self.assertRaises(StorageError):map_product(sample(),identifier,uuid4())
        for field,value in [('BrandPartCode',''),('Category',{'CategoryID':'1'})]:
            data=sample();data['data']['GeneralInfo'][field]=value
            with self.assertRaises(StorageError):map_product(data,{},uuid4())
        data=sample();data['data']['FeaturesGroups'][0]['Features'].append(deepcopy(data['data']['FeaturesGroups'][0]['Features'][1]))
        e=map_product(data,{},uuid4())
        self.assertNotIn('ram',{f.field for f in e.fields})
        self.assertTrue(any('multiple' in issue for issue in e.issues))
    def test_unsupported_units_and_zero_are_unknown_not_guessed(self):
        data=sample();features=data['data']['FeaturesGroups'][0]['Features']
        features[1]['Feature']['Measure']['Signs']['_']='MB';features[3]['RawValue']='0'
        e=map_product(data,{},uuid4())
        self.assertNotIn('ram',{f.field for f in e.fields});self.assertNotIn('storage',{f.field for f in e.fields})

class HttpTests(unittest.TestCase):
    def run_response(self,response):
        requests=[]
        def handle(request):requests.append(request);return response
        with patch.dict(os.environ,{'PDW_ICECAT_USERNAME':'example-user','PDW_ICECAT_API_TOKEN':'server-only-token'}):
            with httpx.Client(transport=httpx.MockTransport(handle)) as client:
                result=fetch_product({'Brand':'Example','ProductCode':'ABC#US'},client)
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0].url.host,'live.icecat.biz')
        self.assertNotIn('server-only-token',str(requests[0].url))
        self.assertEqual(requests[0].headers['api-token'],'server-only-token')
        self.assertEqual(requests[0].url.params['ProductCode'],'ABC#US')
        return result
    def test_fixed_host_header_credentials_and_encoded_suffix(self):
        self.assertEqual(self.run_response(httpx.Response(200,json=sample()))['msg'],'OK')
    def test_failure_types_no_redirects_no_raw_provider_errors(self):
        for status,body,expected in [(404,{'StatusCode':8},'product_not_found'),(403,{'StatusCode':9},'product_restricted'),
                                     (429,{},'import_busy'),(500,{},'import_unavailable'),(302,{},'import_unavailable')]:
            with self.assertRaises(StorageError) as raised:self.run_response(httpx.Response(status,json={**body,'Message':'secret'}))
            self.assertEqual(raised.exception.code,expected);self.assertNotIn('secret',raised.exception.message)
        for response in [httpx.Response(200,text='<html>login</html>'),httpx.Response(200,headers={'content-type':'application/json'},content=b'x'*(MAX_BYTES+1))]:
            with self.assertRaises(StorageError):self.run_response(response)

class PreviewRepo:
    def __init__(self):self.receipts={};self.calls=0
    def import_preview(self,owner,key):return self.receipts.get((owner,key))
    def limit_imports(self,owner):self.calls+=1
    def store_import_preview(self,owner,key,identifier,evidence):
        self.receipts[owner,key]={'identifier':identifier,'evidence':evidence};return evidence

class PreviewApiTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'PDW_AUTH_MODE':'local','PDW_LOCAL_STORAGE':'1'});self.env.start()
        self.repo=PreviewRepo();app.dependency_overrides[repository]=lambda:self.repo
        self.web=TestClient(app)
    def tearDown(self):self.web.close();app.dependency_overrides.clear();self.env.stop()
    def test_preview_is_idempotent_and_does_not_save_a_workspace(self):
        body={'request_id':str(uuid4()),'mode':'id','value':'123'}
        with patch.object(import_api,'fetch_product',return_value=sample()) as fetch:
            a=self.web.post('/api/v1/imports/preview',json=body);b=self.web.post('/api/v1/imports/preview',json=body)
            self.assertEqual(a.status_code,200,a.text);self.assertEqual(a.json(),b.json());self.assertEqual(fetch.call_count,1)
            body['value']='124';self.assertEqual(self.web.post('/api/v1/imports/preview',json=body).status_code,409)
    def test_cross_origin_rejected_before_provider_call(self):
        with patch.object(import_api,'fetch_product') as fetch:
            response=self.web.post('/api/v1/imports/preview',headers={'Origin':'https://evil.example'},json={'request_id':str(uuid4()),'mode':'id','value':'123'})
            self.assertEqual(response.status_code,403);fetch.assert_not_called()

class EvidenceValidationTests(unittest.TestCase):
    def test_forged_or_foreign_evidence_cannot_be_saved(self):
        from types import SimpleNamespace
        e=map_product(sample(),{},uuid4()).model_dump(mode='json')
        class Decisions:
            def find_one(self,*args):return None
        repo=SimpleNamespace(import_preview=lambda owner,key: {'evidence':e} if owner=='a' else None,decisions=Decisions())
        state={'records':[{'draft':{'evidence':e},'confirmed':None}]}
        MongoRepository.validate_import_evidence(repo,'a',state)
        with self.assertRaises(StorageError):MongoRepository.validate_import_evidence(repo,'b',state)
        forged=deepcopy(state);forged['records'][0]['draft']['evidence']['fields'][0]['raw']='forged'
        with self.assertRaises(StorageError):MongoRepository.validate_import_evidence(repo,'a',forged)


class BackwardCompatibilityTests(unittest.TestCase):
    def test_old_confirmed_workspaces_accept_new_optional_fields_without_reconfirmation(self):
        from backend.tests.test_storage import state_fixture
        from backend.app.workspaces import WorkspaceState, ensure_candidate_revisions
        old=state_fixture()
        for record in old['records']:
            for laptop in (record['draft'],record['confirmed']):
                for key in ('display','maxRam','batteryWh','evidence'):laptop.pop(key,None)
        normalized=WorkspaceState.model_validate(old).model_dump(mode='json')
        ensure_candidate_revisions(old,normalized)

@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'), 'Set PDW_TEST_MONGO_URI for real Mongo import checks.')
class MongoImportTests(unittest.TestCase):
    def setUp(self):
        from pymongo import MongoClient
        self.client=MongoClient(os.environ['PDW_TEST_MONGO_URI'],serverSelectionTimeoutMS=2000,tz_aware=True)
        self.database_name='pdw_test_'+uuid4().hex
        self.repo=MongoRepository(self.client[self.database_name])
    def tearDown(self):
        self.client.drop_database(self.database_name);self.client.close()
    def test_receipts_are_private_immutable_idempotent_and_expire(self):
        from datetime import datetime,timedelta,timezone
        key=str(uuid4());e=map_product(sample(),{},key).model_dump(mode='json');q={'icecat_id':'123'}
        self.assertEqual(self.repo.store_import_preview('a',key,q,e),e)
        self.assertEqual(self.repo.store_import_preview('a',key,q,{**e,'brand':'changed'}),e)
        self.assertIsNone(self.repo.import_preview('b',key))
        state={'records':[{'draft':{'evidence':e},'confirmed':None}]}
        with self.assertRaises(StorageError):self.repo.validate_import_evidence('b',state)
        self.repo.import_receipts.update_one({'_id':f'a:{key}'},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
        self.assertIsNone(self.repo.import_preview('a',key))
        with self.assertRaises(StorageError):self.repo.validate_import_evidence('a',state)
    def test_saved_evidence_and_history_survive_receipt_expiry_and_refresh(self):
        from backend.tests.test_storage import state_fixture
        from backend.app.workspaces import WorkspaceState,build_snapshot
        key=str(uuid4());e=map_product(sample(),{},key).model_dump(mode='json')
        self.repo.store_import_preview('a',key,{},e)
        state=state_fixture();record=state['records'][1]
        record['draft']['evidence']=e;record['confirmed']['evidence']=deepcopy(e)
        saved=self.repo.create('a',uuid4(),WorkspaceState.model_validate(state).model_dump(mode='json'))
        history=self.repo.save_snapshot('a',build_snapshot(saved,uuid4()))
        self.repo.import_receipts.delete_many({})  # Only this randomly named test database.
        record['draft']['ram']='24';record['confirmed']=deepcopy(record['draft']);record['revision']=2
        newer=self.repo.update('a',saved['id'],1,WorkspaceState.model_validate(state).model_dump(mode='json'))
        self.assertEqual(newer['state']['records'][1]['confirmed']['ram'],'24')
        frozen=self.repo.find_snapshot('a',saved['id'],history['id'])
        self.assertEqual(frozen['state']['records'][1]['confirmed']['ram'],'16')
        self.assertEqual(frozen['state']['records'][1]['confirmed']['evidence'],e)
        # Copying one's saved workspace remains supported after receipt cleanup.
        self.repo.create('a',uuid4(),newer['state'])
        with self.assertRaises(StorageError):self.repo.create('b',uuid4(),newer['state'])
    def test_request_limit_is_per_owner_and_has_bounded_retention(self):
        for _ in range(10):self.repo.limit_imports('a')
        with self.assertRaises(StorageError):self.repo.limit_imports('a')
        self.repo.limit_imports('b')
        self.assertEqual(self.repo.import_limits.count_documents({}),2)
