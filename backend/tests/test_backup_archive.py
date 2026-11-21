"""Encrypted sample archives, current suppression and isolated restore guards."""
from copy import deepcopy
import os
import unittest
from unittest.mock import MagicMock
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from bson import ObjectId
from backend.app import backup_archive as backup

STAMP=1_795_000_000


def sample():
    return {'users':[{'_id':'a','state':'active','email':'PRIVATE@example.invalid','subject':'fixture|a'},
                     {'_id':'b','state':'active','email':'other@example.invalid'}],
            'decisions':[{'_id':'a:keep','owner_id':'a','id':'keep','revision':3,'state':{'title':'PRIVATE work'}},
                         {'_id':'a:gone','owner_id':'a','id':'gone','revision':2,'state':{'title':'deleted work'}},
                         {'_id':'b:private','owner_id':'b','id':'private','revision':1,'state':{'title':'other work'}}],
            'snapshots':[{'_id':'a:keep:r','owner_id':'a','decision_id':'keep','id':'r','state':{'marker':ObjectId()}},
                         {'_id':'a:gone:r','owner_id':'a','decision_id':'gone','id':'r','state':{}}],
            'deletion_ledger':[]}


def controls():
    return {'source_id':'fixture','captured_at':STAMP,'users':deepcopy(sample()['users']),
            'deletion_ledger':[{'_id':'workspace:a:gone','kind':'workspace','owner_id':'a','decision_id':'gone'},
                               {'_id':'account:b','kind':'account','owner_id':'b','active_purged_at':STAMP,
                                'backup_removal_due':STAMP+backup.RETENTION_SECONDS}]}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.key=AESGCM.generate_key(bit_length=256)
        self.rows=sample();self.blob=backup.seal(self.rows,self.key,'fixture',clock=STAMP)
        self.payload=backup.open_archive(self.blob,self.key,clock=STAMP)

    def test_confidential_authenticated_round_trip_preserves_bson_and_uses_fresh_nonce(self):
        self.assertEqual(self.payload['collections'],self.rows)
        self.assertNotIn(b'PRIVATE',self.blob)
        self.assertNotEqual(self.blob,backup.seal(self.rows,self.key,'fixture',clock=STAMP))
        for changed,key in [(self.blob[:-1]+bytes([self.blob[-1]^1]),self.key),
                            (self.blob,AESGCM.generate_key(bit_length=256)),(b'wrong'+self.blob[5:],self.key)]:
            with self.assertRaises(backup.BackupError):backup.open_archive(changed,key,clock=STAMP)

    def test_exercise_workspace_meets_real_application_contract(self):
        from backend.app.workspaces import WorkspaceState
        state=WorkspaceState.model_validate(backup.sample_workspace())
        self.assertEqual(state.plan.savings,'300');self.assertEqual(state.records[1].revision,2)

    def test_exact_expiry_and_future_timestamps_fail_closed(self):
        backup.open_archive(self.blob,self.key,clock=STAMP+backup.RETENTION_SECONDS-1)
        for stamp in (STAMP-31,STAMP+backup.RETENTION_SECONDS):
            with self.assertRaises(backup.BackupError):backup.open_archive(self.blob,self.key,clock=stamp)

    def test_credentials_and_transient_collections_are_not_archivable(self):
        for extra in ('app_sessions','login_flows','maintenance_nonces','system_status','import_receipts'):
            with self.assertRaises(backup.BackupError):backup.seal({**self.rows,extra:[]},self.key,'fixture',clock=STAMP)
        with self.assertRaises(backup.BackupError):backup.seal(self.rows,b'x'*16,'fixture',clock=STAMP)

    def test_new_deletions_suppress_old_data_and_keep_deadlines_without_source_changes(self):
        current=controls();before=deepcopy((self.payload,current))
        plan=backup.restore_plan(self.payload,current,clock=STAMP)
        self.assertEqual([row['id'] for row in plan['decisions'] if not row.get('deleted')],['keep'])
        self.assertNotIn('state',next(row for row in plan['decisions'] if row['id']=='gone'))
        self.assertEqual([row['decision_id'] for row in plan['snapshots']],['keep'])
        self.assertEqual(next(row for row in plan['users'] if row['_id']=='b')['state'],'deleted')
        marker=next(row for row in plan['deletion_ledger'] if row['_id']=='account:b')
        self.assertEqual(marker['backup_removal_due'],STAMP+backup.RETENTION_SECONDS)
        self.assertEqual((self.payload,current),before)

    def test_new_pending_deletion_and_exact_boundary_override_old_active_user(self):
        current=controls();current['deletion_ledger']=[]
        current['users'][0].update(state='pending_deletion',delete_after=STAMP+1,delete_requested_at=STAMP-10,
                                   deletion_notice={'status':'queued'})
        before=backup.restore_plan(self.payload,current,clock=STAMP)
        user=next(row for row in before['users'] if row['_id']=='a')
        self.assertEqual(user['state'],'pending_deletion');self.assertEqual(user['delete_after'],STAMP+1)
        self.assertNotIn('deletion_notice',user);self.assertIn('lifecycle_version',user)
        after=backup.restore_plan(self.payload,current,clock=STAMP+1)
        self.assertFalse(any(row['owner_id']=='a' for row in after['decisions']))
        self.assertTrue(any(row['_id']=='account:a' for row in after['deletion_ledger']))

    def test_current_restoration_cancels_old_pending_state_without_replaying_email(self):
        self.payload['collections']['users'][0].update(state='pending_deletion',delete_after=STAMP+100,
                                                      deletion_notice={'status':'queued'})
        plan=backup.restore_plan(self.payload,controls(),clock=STAMP)
        row=next(row for row in plan['users'] if row['_id']=='a')
        self.assertEqual(row['state'],'active');self.assertNotIn('delete_after',row)
        self.assertNotIn('deletion_notice',row)

    def test_missing_stale_or_cross_source_controls_are_rejected(self):
        for changed in ({'source_id':'wrong'},{'captured_at':STAMP-301},{'captured_at':STAMP+1},
                        {'users':None},{'deletion_ledger':None}):
            with self.assertRaises(backup.BackupError):backup.restore_plan(self.payload,{**controls(),**changed},clock=STAMP)

    def test_purge_retry_subject_and_immutable_deadline_survive_in_quarantine(self):
        current=controls();current['users'][1].update(state='purging',subject='fixture|pending-provider',
            delete_after=STAMP-20,delete_requested_at=STAMP-100,purge_lease='old',purge_lease_until=STAMP+100)
        old={**current['deletion_ledger'][1],'backup_removal_due':STAMP+100}
        self.payload['collections']['deletion_ledger']=[old]
        plan=backup.restore_plan(self.payload,current,clock=STAMP)
        user=next(row for row in plan['users'] if row['_id']=='b')
        self.assertEqual(user['state'],'purging');self.assertEqual(user['subject'],'fixture|pending-provider')
        self.assertNotIn('purge_lease',user)
        self.assertEqual(next(row for row in plan['deletion_ledger'] if row['_id']=='account:b')['backup_removal_due'],STAMP+100)

    def test_unsafe_or_nonempty_targets_are_rejected_before_any_write(self):
        target=MagicMock();target.name='pdw_staging'
        with self.assertRaises(backup.BackupError):backup.restore_test_database(target,self.rows)
        target.list_collection_names.assert_not_called();target.create_collection.assert_not_called()
        target.name='pdw_restore_test_'+'a'*32;target.list_collection_names.return_value=['existing']
        with self.assertRaises(backup.BackupError):backup.restore_test_database(target,self.rows)
        target.create_collection.assert_not_called()

    def test_missing_current_owner_and_malformed_archive_fail_closed(self):
        current=controls();current['users']=[]
        plan=backup.restore_plan(self.payload,current,clock=STAMP)
        self.assertEqual(plan['decisions'],[]);self.assertEqual(plan['snapshots'],[])
        for name,change in [('users',lambda rows:rows.append(deepcopy(rows[0]))),
                            ('snapshots',lambda rows:rows[0].update(decision_id='unknown',_id='a:unknown:r')),
                            ('decisions',lambda rows:rows[0].update(owner_id='wrong'))]:
            invalid=deepcopy(self.rows);change(invalid[name])
            with self.assertRaises(backup.BackupError):backup.seal(invalid,self.key,'fixture',clock=STAMP)

    def test_local_connection_guard_rejects_hosted_credential_and_multi_host_uris(self):
        for uri in ('mongodb+srv://example.com','mongodb://remote:27017','mongodb://u:p@localhost',
                    'mongodb://127.0.0.1:27017,remote:27017','mongodb://localhost/?tls=false',
                    'mongodb://localhost/pdw_staging','mongodb://localhost:65536'):
            with self.assertRaises(backup.BackupError):backup.local_uri(uri)
        self.assertEqual(backup.local_uri('mongodb://127.0.0.1:27017'),'mongodb://127.0.0.1:27017')


@unittest.skipUnless(os.environ.get('PDW_TEST_MONGO_URI'),'Set PDW_TEST_MONGO_URI for disposable backup integration exercise.')
class MongoBackupTests(unittest.TestCase):
    def test_encrypted_isolated_restore_with_newer_deletions_and_no_restored_sessions(self):
        report=backup.exercise(os.environ['PDW_TEST_MONGO_URI'])
        self.assertEqual(report['status'],'ok');self.assertEqual(report['restored_visible_workspaces'],1)
        self.assertEqual(report['restored_reviews'],1);self.assertEqual(report['restored_sessions'],0)
        self.assertTrue(report['source_unchanged_by_restore']);self.assertFalse(report['durable_live_backup_created'])
