"""Storage API behavior; shared suite also runs against real Mongo when requested."""
from copy import deepcopy
from threading import Lock
from uuid import uuid4
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.storage_api import repository
from backend.app.workspaces import StorageError, ensure_candidate_revisions, now


def state_fixture():
    def laptop(key, current=False):
        return dict(id=key,current=current,name='Current' if current else 'Candidate A',configuration='Exact build',cpu='',os='',ram='8' if current else '16',storage='256' if current else '512',compatible='yes',costMode='components',price='0' if current else '800',tax='0',shipping='0',other='0',provisional='',weight='',battery='',batteryContext='',source='https://example.com/laptop',notes='Fictional evidence',display='',maxRam='',batteryWh='',evidence=None)
    baseline, candidate = laptop('current',True), laptop('a')
    return dict(schemaVersion=1,title='Test decision',timezone='America/Los_Angeles',tasks=[],customNeeds='',
      requirements=dict(ram='16',storage='512',ceiling='900',noLimit=False,compatibility=True),
      preferences=dict(performance='high',portability='medium',battery='medium',repairability='low',cost='ignored'),
      records=[dict(draft=baseline,confirmed=deepcopy(baseline),revision=1),dict(draft=candidate,confirmed=deepcopy(candidate),revision=1)],
      plan=dict(savings='300',contribution='150',firstDate='2027-01-31',targetDate='2027-03-31',essential=False,useBudget=False,income='1600',housing='700',food='250',transportation='180',other='120',goals='150',buffer='50',useScenario=False,category='transportation',reduction='40',allocation='40'),
      outcome='Investigate and save',reason='Compare before buying.')


class MemoryRepository:
    """Test double only; never a silent fallback when the database is unavailable."""
    def __init__(self):
        self.decisions, self.snapshots = {}, {}
        self.lock = Lock()
    def create(self, owner, request_id, state):
        key = (owner,str(request_id))
        with self.lock:
            self.decisions.setdefault(key,dict(id=str(request_id),revision=1,schema_version=1,state=deepcopy(state),created_at=now(),updated_at=now()))
            return deepcopy(self.decisions[key])
    def get(self, owner, key):
        if (owner,key) not in self.decisions:
            raise StorageError(404,'not_found','Not found')
        return deepcopy(self.decisions[owner,key])
    def list(self, owner, offset, limit):
        return [dict(id=d['id'],title=d['state']['title'],revision=d['revision'],updated_at=d['updated_at']) for (o,_),d in self.decisions.items() if o==owner][offset:offset+limit]
    def update(self, owner, key, expected, state):
        with self.lock:
            prior=self.get(owner,key)
            if prior['revision'] != expected:
                raise StorageError(409,'revision_conflict','Revision conflict')
            ensure_candidate_revisions(prior['state'],state)
            prior.update(state=deepcopy(state),revision=expected+1,updated_at=now())
            self.decisions[owner,key]=prior
            return deepcopy(prior)
    def find_snapshot(self,owner,decision_id,snapshot_id):
        return deepcopy(self.snapshots.get((owner,decision_id,snapshot_id)))
    def save_snapshot(self,owner,snapshot):
        with self.lock:
            return deepcopy(self.snapshots.setdefault((owner,snapshot['decision_id'],snapshot['id']),deepcopy(snapshot)))
    def list_snapshots(self,owner,decision_id,offset,limit):
        self.get(owner,decision_id)
        return [dict(id=s['id'],title=s['state']['title'],decision_revision=s['decision_revision'],created_at=s['created_at']) for (o,d,_),s in self.snapshots.items() if o==owner and d==decision_id][offset:offset+limit]


class StorageBehavior:
    def setUp(self):
        self.auth_env=patch.dict(os.environ,{'PDW_AUTH_MODE':'local','PDW_LOCAL_STORAGE':'1'})
        self.auth_env.start()
        self.repo = self.make_repository()
        app.dependency_overrides[repository] = lambda:self.repo
        self.client=TestClient(app)
        self.state=state_fixture()
    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.cleanup()
        self.auth_env.stop()
    def cleanup(self):
        pass
    def create(self):
        response=self.client.post('/api/v1/decisions',json={'request_id':str(uuid4()),'state':self.state})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()
    def test_roundtrip_and_summary_omit_financial_details(self):
        created=self.create()
        result=self.client.get('/api/v1/decisions/'+created['id']).json()
        self.assertEqual(result['state'],self.state)
        listing=self.client.get('/api/v1/decisions').json()['items']
        self.assertEqual(len(listing),1)
        self.assertEqual(set(listing[0]),{'id','title','revision','updated_at'})
    def test_stale_save_does_not_overwrite(self):
        created=self.create(); path='/api/v1/decisions/'+created['id']
        changed=deepcopy(self.state); changed['reason']='New reason'
        self.assertEqual(self.client.patch(path,json={'expected_revision':1,'state':changed}).status_code,200)
        response=self.client.patch(path,json={'expected_revision':1,'state':self.state})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.client.get(path).json()['state']['reason'],'New reason')
    def test_history_is_server_calculated_and_immutable(self):
        created=self.create(); path='/api/v1/decisions/'+created['id']
        saved=self.client.post(path+'/snapshots',json={'request_id':str(uuid4()),'expected_revision':1})
        self.assertEqual(saved.status_code,201,saved.text)
        snapshot=saved.json()
        self.assertEqual(snapshot['evaluation']['candidates'][1]['base_plan']['contributions'],4)
        self.assertEqual(snapshot['evaluation_input']['plan']['contribution_cents'],15000)
        changed=deepcopy(self.state);changed['plan']['contribution']='190';changed['reason']='Later reason'
        self.client.patch(path,json={'expected_revision':1,'state':changed})
        result=self.client.get(path+'/snapshots/'+snapshot['id']).json()
        self.assertEqual(result,snapshot)
        self.assertEqual(result['state']['reason'],'Compare before buying.')
        self.assertEqual(self.client.patch(path+'/snapshots/'+snapshot['id'],json={}).status_code,405)
    def test_create_and_snapshot_retry_are_idempotent(self):
        request_id=str(uuid4());payload={'request_id':request_id,'state':self.state}
        a=self.client.post('/api/v1/decisions',json=payload).json()
        b=self.client.post('/api/v1/decisions',json=payload).json()
        self.assertEqual(a,b)
        path='/api/v1/decisions/'+a['id']
        snapshot_payload={'request_id':str(uuid4()),'expected_revision':1}
        first=self.client.post(path+'/snapshots',json=snapshot_payload).json()
        self.client.patch(path,json={'expected_revision':1,'state':self.state})
        again=self.client.post(path+'/snapshots',json=snapshot_payload).json()
        self.assertEqual(first,again)
        self.assertEqual(len(self.client.get(path+'/snapshots').json()['items']),1)
    def test_stale_snapshot_and_client_results_rejected(self):
        created=self.create();path='/api/v1/decisions/'+created['id']+'/snapshots'
        self.assertEqual(self.client.post(path,json={'expected_revision':2,'request_id':str(uuid4())}).status_code,409)
        self.assertEqual(self.client.post(path,json={'expected_revision':1,'request_id':str(uuid4()),'evaluation':{}}).status_code,422)
    def test_pending_drafts_do_not_enter_saved_evaluation(self):
        self.state['records'][1]['draft']['price']='1000'
        created=self.create();path='/api/v1/decisions/'+created['id']+'/snapshots'
        result=self.client.post(path,json={'expected_revision':1,'request_id':str(uuid4())}).json()
        self.assertEqual(result['evaluation']['candidates'][1]['cost_cents'],80000)
        self.assertEqual(result['state']['records'][1]['draft']['price'],'1000')
    def test_invalid_unfinished_plan_can_save_but_cannot_capture(self):
        self.state['plan']['contribution']=''
        created=self.create()
        response=self.client.post('/api/v1/decisions/'+created['id']+'/snapshots',json={'expected_revision':1,'request_id':str(uuid4())})
        self.assertEqual(response.status_code,422)
    def test_ownership_comes_from_server_and_cross_origin_denied(self):
        created=self.create()
        with self.assertRaises(StorageError):self.repo.get('another-owner',created['id'])
        self.assertEqual(self.repo.list('another-owner',0,20),[])
        response=self.client.get('/api/v1/decisions',headers={'Origin':'https://untrusted.example'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.post('/api/v1/decisions',json={'request_id':str(uuid4()),'state':self.state,'owner_id':'victim'}).status_code,422)
    def test_candidate_revision_must_advance_on_confirmation_change(self):
        created=self.create();changed=deepcopy(self.state)
        changed['records'][1]['confirmed']['ram']='32'
        path='/api/v1/decisions/'+created['id']
        self.assertEqual(self.client.patch(path,json={'expected_revision':1,'state':changed}).status_code,422)
        changed['records'][1]['revision']=2
        self.assertEqual(self.client.patch(path,json={'expected_revision':1,'state':changed}).status_code,200)
    def test_invalid_state_and_unsafe_source_are_rejected(self):
        for transform in [lambda s:s.update(timezone='Invalid/Zone'),lambda s:s['records'][0]['draft'].update(current=False),lambda s:s['records'][1]['draft'].update(source='javascript:alert(1)')]:
            state=deepcopy(self.state);transform(state)
            self.assertEqual(self.client.post('/api/v1/decisions',json={'request_id':str(uuid4()),'state':state}).status_code,422)


class MemoryStorageTests(StorageBehavior,unittest.TestCase):
    def make_repository(self):return MemoryRepository()


@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI to run real Mongo integration tests.')
class MongoStorageTests(StorageBehavior,unittest.TestCase):
    def make_repository(self):
        from pymongo import MongoClient
        from backend.app.repositories import MongoRepository
        self.mongo_client=MongoClient(os.environ['PDW_TEST_MONGO_URI'],serverSelectionTimeoutMS=2000)
        self.database_name='pdw_test_'+uuid4().hex
        return MongoRepository(self.mongo_client[self.database_name])
    def cleanup(self):
        # Only the fresh, randomly named test database created above is removed.
        self.mongo_client.drop_database(self.database_name)
        self.mongo_client.close()
    def test_database_survives_repository_recreation(self):
        from backend.app.repositories import MongoRepository
        created=self.create()
        recreated=MongoRepository(self.mongo_client[self.database_name])
        self.assertEqual(recreated.get('local-development-user',created['id'])['state'],self.state)
    def test_parallel_updates_only_one_wins(self):
        from concurrent.futures import ThreadPoolExecutor
        created=self.create()
        def update(_):
            try:
                self.repo.update('local-development-user',created['id'],1,self.state)
                return 200
            except StorageError as err:return err.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(update,range(2))),[200,409])


class StorageGateTests(unittest.TestCase):
    def test_storage_disabled_by_default(self):
        with patch.dict(os.environ,{'PDW_LOCAL_STORAGE':'0'}),TestClient(app) as client:
            self.assertEqual(client.get('/api/v1/decisions').status_code,503)
