"""Capture failures never fall back to an inconsistent read or write source data."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

from backend.app import backup_archive as archive
from backend.app import backup_capture as capture


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.database=MagicMock();self.db=self.database.with_options.return_value
        self.collections={name:MagicMock() for name in archive.COLLECTIONS}
        self.db.__getitem__.side_effect=self.collections.__getitem__
        self.session=self.database.client.start_session.return_value.__enter__.return_value
        self.rows={name:[] for name in archive.COLLECTIONS}
        self.rows['users']=[{'_id':'fixture','state':'active'}]
        self.rows['decisions']=[{'_id':'fixture:work','owner_id':'fixture','id':'work','state':{'title':'fictional'}}]
        self.cursors={}
        for name in archive.COLLECTIONS:
            cursor=MagicMock()
            cursor.__enter__.return_value=cursor
            cursor.__iter__.side_effect=lambda name=name:iter(self.rows[name])
            self.cursors[name]=cursor
            self.db[name].find.return_value.batch_size.return_value.max_time_ms.return_value=cursor

    def test_one_snapshot_preserves_owned_data_without_source_mutation(self):
        before=deepcopy(self.rows)
        blob=capture.capture_archive(self.database,b'k'*32,'fixture',clock=1_795_000_000)
        result=archive.open_archive(blob,b'k'*32,clock=1_795_000_000)
        self.assertEqual(result['collections'],before);self.assertEqual(self.rows,before)
        self.database.client.start_session.assert_called_once_with(snapshot=True)
        self.assertEqual(self.db.__getitem__.call_args_list[-4:],[unittest.mock.call(n) for n in archive.COLLECTIONS])
        for name in archive.COLLECTIONS:
            self.db[name].find.assert_called_once_with({},session=self.session)
        # All source operations are reads; no generic write helper is used.
        self.assertFalse(any(any(op in str(call) for op in ('insert','update','delete','drop')) for call in self.database.mock_calls))

    def test_snapshot_failure_is_redacted_and_does_not_fall_back(self):
        self.database.client.start_session.side_effect=RuntimeError('PRIVATE URI password')
        with self.assertRaises(archive.BackupError) as raised:
            capture.capture_archive(self.database,b'k'*32,'fixture')
        self.assertNotIn('PRIVATE',str(raised.exception));self.db['users'].find.assert_not_called()

    def test_mid_capture_failure_returns_no_partial_archive(self):
        self.cursors['decisions'].__iter__.side_effect=RuntimeError('private provider response')
        with self.assertRaises(archive.BackupError):capture.capture_archive(self.database,b'k'*32,'fixture')
        self.database.client.start_session.assert_called_once()
        self.db['snapshots'].find.assert_not_called()

    def test_row_and_byte_limits_stop_before_upload_or_unbounded_accumulation(self):
        for setting in ({'MAX_ROWS':0},{'MAX_BYTES':4100}):
            with self.subTest(setting=setting),patch.multiple(capture,**setting),self.assertRaises(archive.BackupError):
                capture.capture_archive(self.database,b'k'*32,'fixture')

    def test_bad_configuration_never_reads_source(self):
        with self.assertRaises(archive.BackupError):capture.capture_archive(self.database,b'short','fixture')
        self.database.with_options.assert_not_called()

    def test_orphaned_rows_fail_closed(self):
        self.rows['users']=[]
        with self.assertRaises(archive.BackupError):capture.capture_archive(self.database,b'k'*32,'fixture')
