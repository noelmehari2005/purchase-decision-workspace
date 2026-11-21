"""Expiry evidence requires a complete version listing, never merely a 404."""
import json
import unittest
import httpx

from backend.app import backup_retention as retention
from backend.app.backup_storage import BUCKET_ID, BUCKET_NAME, BackupStorageError


class RetentionTests(unittest.TestCase):
    def setUp(self):self.files=[];self.extra={};self.calls=[];self.status=200

    def handler(self,request):
        self.calls.append(request)
        if len(self.calls)==1:
            return httpx.Response(200,json={'authorizationToken':'fake-reader-token','apiInfo':{'storageApi':{
                'apiUrl':'https://api005.backblazeb2.com','allowed':{
                    'buckets':[{'id':BUCKET_ID,'name':BUCKET_NAME}],'namePrefix':'archives/',
                    'capabilities':['listBuckets','listFiles','readFiles']}}}})
        self.assertEqual(request.url.path,'/b2api/v4/b2_list_file_versions')
        self.assertEqual(json.loads(request.content),{'bucketId':BUCKET_ID,'prefix':retention.PROBE,'maxFileCount':100})
        return httpx.Response(self.status,json={'files':self.files,**self.extra})

    def factory(self,**kwargs):return httpx.Client(transport=httpx.MockTransport(self.handler),**kwargs)
    def check(self):return retention.check_probe('id','fake-secret',client_factory=self.factory)

    def test_complete_empty_version_listing_confirms_only_probe_expiry(self):
        result=self.check()
        self.assertTrue(result['probe_expiry_verified']);self.assertFalse(result['real_archive_expiry_verified'])
        self.assertFalse(result['deletion_requested_by_command']);self.assertEqual(len(self.calls),2)

    def test_hidden_versions_or_markers_are_not_reported_as_removed(self):
        for actions in (['upload'],['hide'],['upload','upload','hide']):
            self.calls=[];self.files=[{'fileName':retention.PROBE,'action':a} for a in actions]
            result=self.check();self.assertFalse(result['probe_expiry_verified'])
            self.assertEqual(result['probe_versions_present'],len(actions))

    def test_pagination_malformed_or_out_of_scope_listing_never_proves_expiry(self):
        for extra in ({'nextFileName':'more'},{'nextFileId':'more'},{'files':None},
                      {'files':[{'fileName':'real-archive','action':'upload'}]},
                      {'files':[{'fileName':retention.PROBE,'action':'unknown'}]}):
            self.calls=[];self.extra=extra
            with self.subTest(extra=extra),self.assertRaises(BackupStorageError):self.check()

    def test_not_found_or_forbidden_never_counts_as_expired(self):
        for status in (404,403,503):
            self.calls=[];self.status=status
            with self.subTest(status=status),self.assertRaises(BackupStorageError):self.check()
