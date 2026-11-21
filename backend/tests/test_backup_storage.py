"""Mock B2 only: never reads secrets or sends real uploads."""
from copy import deepcopy
import hashlib
import json
import unittest

import httpx
from backend.app import backup_archive as archive
from backend.app import backup_storage as storage

STAMP=1_795_000_000


class BackupStorageTests(unittest.TestCase):
    def setUp(self):
        self.key=b'k'*32
        self.blob=archive.seal({name:[] for name in archive.COLLECTIONS},self.key,'fixture',clock=STAMP)
        self.auth={'apiInfo':{'storageApi':{'apiUrl':'https://api005.backblazeb2.com','allowed':{
            'buckets':[{'id':storage.BUCKET_ID,'name':storage.BUCKET_NAME}],
            'namePrefix':'archives/','capabilities':['writeFiles']}}},'authorizationToken':'account-token'}
        self.upload={'bucketId':storage.BUCKET_ID,'uploadUrl':'https://pod-000-1007-13.backblaze.com/b2api/v4/b2_upload_file/'+storage.BUCKET_ID+'/c001_v0001',
                     'authorizationToken':'upload-token'}
        self.requests=[];self.options={};self.reply_change=None;self.failure_at=None

    def handler(self,request):
        self.requests.append(request)
        if self.failure_at==len(self.requests):
            return httpx.Response(503,text='PRIVATE key profile provider details',headers={'Location':'https://evil.invalid'})
        if len(self.requests)==1:return httpx.Response(200,json=self.auth)
        if len(self.requests)==2:return httpx.Response(200,json=self.upload)
        result={'bucketId':storage.BUCKET_ID,'fileName':request.headers['X-Bz-File-Name'],'fileId':'opaque-version-id',
                'contentLength':len(request.content),'contentSha1':hashlib.sha1(request.content).hexdigest()}
        if self.reply_change:result.update(self.reply_change)
        return httpx.Response(200,json=result)

    def factory(self,**kwargs):
        self.options=kwargs
        return httpx.Client(transport=httpx.MockTransport(self.handler),**kwargs)

    def run_upload(self,**kwargs):
        return storage.upload_archive(kwargs.pop('blob',self.blob),kwargs.pop('encryption_key',self.key),
                                      'private-key-id','private-key',client_factory=self.factory,clock=STAMP,**kwargs)

    def test_only_encrypted_bytes_and_safe_metadata_are_transmitted(self):
        result=self.run_upload()
        self.assertEqual(len(self.requests),3)
        first,second,last=self.requests
        self.assertEqual(first.url,storage.AUTHORIZE)
        self.assertEqual(json.loads(second.content),{'bucketId':storage.BUCKET_ID})
        self.assertEqual(last.content,self.blob)
        self.assertEqual(archive.open_archive(last.content,self.key,clock=STAMP)['source_id'],'fixture')
        self.assertRegex(last.headers['X-Bz-File-Name'],r'^archives/[a-f0-9]{32}\.pdwbackup$')
        self.assertEqual(last.headers['Authorization'],'upload-token')
        self.assertEqual(last.headers['X-Bz-Server-Side-Encryption'],'AES256')
        self.assertNotIn('private-key',str(last.headers))
        self.assertFalse(self.options['follow_redirects']);self.assertFalse(self.options['trust_env'])
        self.assertTrue(result['upload_acknowledged']);self.assertFalse(result['restore_verified'])
        self.assertFalse(result['expiry_verified'])

    def test_bad_expired_or_wrong_key_archive_never_authenticates(self):
        for blob,key in [(b'plaintext',self.key),(self.blob,b'wrong-key'*4),
                         (archive.seal({n:[] for n in archive.COLLECTIONS},self.key,'fixture',clock=STAMP-archive.RETENTION_SECONDS),self.key)]:
            with self.subTest(blob=blob[:4]),self.assertRaises(storage.BackupStorageError):
                self.run_upload(blob=blob,encryption_key=key)
        self.assertEqual(self.requests,[])

    def test_account_wide_other_bucket_and_unrestricted_prefix_are_rejected(self):
        good=deepcopy(self.auth)
        for change in [{'buckets':None},{'buckets':[]},{'buckets':[{'id':'another','name':'other'}]},
                       {'namePrefix':None},{'namePrefix':''},{'namePrefix':'archives'}, {'capabilities':['readFiles']},
                       {'capabilities':['writeFiles','deleteFiles']}, {'capabilities':['writeFiles','writeBucketEncryption']},
                       {'capabilities':['writeFiles','writeBucketLifecycleRules']}]:
            self.auth=deepcopy(good);self.auth['apiInfo']['storageApi']['allowed'].update(change);self.requests=[]
            with self.subTest(change=change),self.assertRaises(storage.BackupStorageError):self.run_upload()
            self.assertEqual(len(self.requests),1)

    def test_untrusted_destinations_stop_before_sending_credentials(self):
        for url in ['http://api005.backblazeb2.com','https://evil.invalid','https://api005.backblazeb2.com.evil.invalid',
                    'https://user@api005.backblazeb2.com','https://api005.backblazeb2.com:443','https://api005.backblazeb2.com?x=1']:
            self.auth['apiInfo']['storageApi']['apiUrl']=url;self.requests=[]
            with self.subTest(url=url),self.assertRaises(storage.BackupStorageError):self.run_upload()
            self.assertEqual(len(self.requests),1)
        self.auth['apiInfo']['storageApi']['apiUrl']='https://api005.backblazeb2.com'
        for url in ['https://evil.invalid/b2api/v4/b2_upload_file','https://pod-1.backblaze.com/other',
                    'https://pod-1.backblaze.com:443/b2api/v4/b2_upload_file']:
            self.upload['uploadUrl']=url;self.requests=[]
            with self.subTest(url=url),self.assertRaises(storage.BackupStorageError):self.run_upload()
            self.assertEqual(len(self.requests),2)

    def test_failures_do_not_retry_or_expose_provider_messages(self):
        for phase in (1,2,3):
            self.requests=[];self.failure_at=phase
            with self.subTest(phase=phase),self.assertRaises(storage.BackupStorageError) as raised:self.run_upload()
            self.assertEqual(len(self.requests),phase);self.assertNotIn('PRIVATE',str(raised.exception))

    def test_unverified_acknowledgements_are_not_success(self):
        for change in [{'bucketId':'other'},{'fileName':'other'},{'contentLength':0},{'contentSha1':'wrong'},{'fileId':None}]:
            self.reply_change=change;self.requests=[]
            with self.subTest(change=change),self.assertRaises(storage.BackupStorageError):self.run_upload()

    def test_redirects_and_oversized_responses_are_rejected(self):
        for status,body in [(302,b''),(200,b'x'*(storage.MAX_RESPONSE_BYTES+1)),(200,b'[]'),(200,b'invalid json')]:
            calls=[]
            def handler(request):
                calls.append(request)
                return httpx.Response(status,content=body,headers={'Location':'https://evil.invalid'})
            def factory(**kwargs):return httpx.Client(transport=httpx.MockTransport(handler),**kwargs)
            with self.subTest(status=status,bytes=len(body)),self.assertRaises(storage.BackupStorageError):
                storage.upload_archive(self.blob,self.key,'id','secret',client_factory=factory,clock=STAMP)
            self.assertEqual(len(calls),1)
