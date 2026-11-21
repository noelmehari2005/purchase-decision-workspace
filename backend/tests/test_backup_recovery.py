"""Reader transport and disposable-target safety; no network or real secrets."""
import hashlib
import time
import unittest
from unittest.mock import MagicMock, patch

import httpx
from backend.app import backup_archive as archive
from backend.app import backup_recovery as recovery
from backend.app.backup_staging import SOURCE
from backend.app.backup_storage import BUCKET_ID, BUCKET_NAME, BackupStorageError


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.blob=b'fictional encrypted bytes';self.name='archives/'+'a'*32+'.pdwbackup'
        self.digest=hashlib.sha256(self.blob).hexdigest();self.calls=[];self.status=200
        self.allowed={'buckets':[{'id':BUCKET_ID,'name':BUCKET_NAME}],'namePrefix':'archives/',
                      'capabilities':['listBuckets','listFiles','readFiles']}
        self.endpoint='https://f005.backblazeb2.com'

    def handler(self,request):
        self.calls.append(request)
        if len(self.calls)==1:
            return httpx.Response(200,json={'apiInfo':{'storageApi':{'allowed':self.allowed,'downloadUrl':self.endpoint}},
                                           'authorizationToken':'fictional-reader-token'})
        self.assertEqual(request.headers['Authorization'],'fictional-reader-token')
        self.assertEqual(request.url.path,'/file/'+BUCKET_NAME+'/'+self.name)
        self.assertNotIn('fictional-secret',str(request.headers))
        return httpx.Response(self.status,content=self.blob,headers={'Location':'https://evil.invalid'})

    def factory(self,**kwargs):
        self.assertFalse(kwargs['follow_redirects']);self.assertFalse(kwargs['trust_env'])
        return httpx.Client(transport=httpx.MockTransport(self.handler),**kwargs)

    def download(self):return recovery.download_archive(self.name,self.digest,'id','fictional-secret',client_factory=self.factory)

    def test_private_download_uses_headers_and_checks_saved_upload_fingerprint(self):
        self.assertEqual(self.download(),self.blob);self.assertEqual(len(self.calls),2)
        self.assertFalse(self.calls[1].url.query)

    def test_wrong_key_scope_or_endpoint_never_sends_download_token(self):
        for change in [{'buckets':None},{'namePrefix':''},{'capabilities':['readFiles','writeFiles']},
                       {'capabilities':['listBuckets','listFiles','readFiles','deleteFiles']}]:
            before=dict(self.allowed);self.allowed.update(change);self.calls=[]
            with self.subTest(change=change),self.assertRaises(BackupStorageError):self.download()
            self.assertEqual(len(self.calls),1);self.allowed=before
        for url in ['https://evil.invalid','http://f005.backblazeb2.com','https://f005.backblazeb2.com:443',
                    'https://f005.backblazeb2.com?token=private']:
            self.endpoint=url;self.calls=[]
            with self.subTest(url=url),self.assertRaises(BackupStorageError):self.download()
            self.assertEqual(len(self.calls),1)

    def test_checksum_mismatch_redirect_and_oversize_are_failures(self):
        self.digest='b'*64
        with self.assertRaises(BackupStorageError):self.download()
        self.digest=hashlib.sha256(self.blob).hexdigest();self.status=302;self.calls=[]
        with self.assertRaises(BackupStorageError):self.download()
        self.assertEqual(len(self.calls),2)
        self.status=200;self.calls=[]
        self.blob=b'x'*100;self.digest=hashlib.sha256(self.blob).hexdigest()
        with patch.object(recovery,'MAX_BYTES',1),self.assertRaises(BackupStorageError):self.download()

    def test_bad_names_and_checksums_never_authenticate(self):
        for name,digest in [('archives/../secret',self.digest),(self.name,'bad'),('https://evil.invalid',self.digest)]:
            with self.assertRaises(BackupStorageError):
                recovery.download_archive(name,digest,'id','secret',client_factory=self.factory)
        self.assertEqual(self.calls,[])

    def payload(self):
        stamp=time.time()
        return {'source_id':SOURCE,'expires_at':stamp+100,'collections':{n:[] for n in archive.COLLECTIONS}},\
               {'source_id':SOURCE,'captured_at':stamp,'users':[],'deletion_ledger':[]}

    def test_remote_target_stale_controls_and_wrong_source_never_connect(self):
        factory=MagicMock();payload,controls=self.payload()
        with self.assertRaises(archive.BackupError):
            recovery.restore_local(payload,controls,uri='mongodb+srv://remote.mongodb.net',client_factory=factory)
        controls['captured_at']-=301
        with self.assertRaises(archive.BackupError):recovery.restore_local(payload,controls,client_factory=factory)
        payload['source_id']='other'
        with self.assertRaises(archive.BackupError):recovery.restore_local(payload,controls,client_factory=factory)
        factory.assert_not_called()

    def test_existing_local_target_is_never_dropped(self):
        factory=MagicMock();client=factory.return_value.__enter__.return_value
        client.__getitem__.return_value.list_collection_names.return_value=['existing']
        with self.assertRaises(archive.BackupError):recovery.restore_local(*self.payload(),client_factory=factory)
        client.drop_database.assert_not_called()

    def test_new_reserved_target_is_removed_even_if_validation_fails(self):
        factory=MagicMock();client=factory.return_value.__enter__.return_value;target=client.__getitem__.return_value
        target.list_collection_names.return_value=[]
        target.restore_manifest.find_one.return_value={'_id':'quarantine'}
        with patch.object(recovery,'restore_test_database'),\
                patch.object(recovery,'verify_local_restore',side_effect=archive.BackupError('bad state')),\
                self.assertRaises(archive.BackupError):recovery.restore_local(*self.payload(),client_factory=factory)
        self.assertRegex(client.drop_database.call_args.args[0],r'^pdw_restore_test_[a-f0-9]{32}$')
