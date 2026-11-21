"""Key creation request/scope tests use fictional values and mock HTTP only."""
import json
import unittest

import httpx
from backend.app import backup_keys as keys
from backend.app.backup_storage import BackupStorageError, BUCKET_ID

STAMP=1_795_000_000


class BackupKeyTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.change={};self.account=keys.ACCOUNT_ID;self.authorized=True

    def handler(self,request):
        self.calls.append(request)
        if len(self.calls)==1:
            return httpx.Response(200,json={'accountId':self.account,'authorizationToken':'fake-account-token',
                'apiInfo':{'storageApi':{'apiUrl':'https://api005.backblazeb2.com',
                                       'allowed':{'capabilities':['writeKeys'] if self.authorized else []}}}})
        body=json.loads(request.content)
        self.assertEqual(body['bucketIds'],[BUCKET_ID]);self.assertEqual(body['namePrefix'],'archives/')
        self.assertEqual(body['validDurationInSeconds'],90*86400)
        return httpx.Response(200,json={**body,'applicationKeyId':'fake-new-id','applicationKey':'fake-new-secret',
                                       'expirationTimestamp':(STAMP+keys.DURATION)*1000,**self.change})

    def factory(self,**kwargs):
        self.assertFalse(kwargs['trust_env']);self.assertFalse(kwargs['follow_redirects'])
        return httpx.Client(transport=httpx.MockTransport(self.handler),**kwargs)

    def test_exact_writer_and_reader_capabilities_without_destructive_permissions(self):
        for kind in ('writer','reader'):
            self.calls=[]
            result=keys.create_key('fake-master-id','fake-master-secret',kind,client_factory=self.factory,clock=STAMP)
            self.assertEqual(result['capabilities'],keys.CAPABILITIES[kind])
            self.assertNotIn('deleteFiles',result['capabilities'])
            self.assertNotIn('fake-master-secret',str(self.calls[1].headers))

    def test_wrong_account_or_missing_creation_rights_stop_before_mutation(self):
        for account,authorized in [('other',True),(keys.ACCOUNT_ID,False)]:
            self.account=account;self.authorized=authorized;self.calls=[]
            with self.assertRaises(BackupStorageError):
                keys.create_key('id','secret','writer',client_factory=self.factory,clock=STAMP)
            self.assertEqual(len(self.calls),1)

    def test_broader_returned_scope_wrong_bucket_and_invalid_expiry_are_rejected(self):
        for change in [{'capabilities':['writeFiles','deleteFiles']},{'bucketIds':None},
                       {'namePrefix':''},{'expirationTimestamp':None},{'expirationTimestamp':STAMP*1000},
                       {'expirationTimestamp':(STAMP+keys.DURATION+301)*1000}]:
            self.calls=[];self.change=change
            with self.subTest(change=change),self.assertRaises(BackupStorageError):
                keys.create_key('id','secret','writer',client_factory=self.factory,clock=STAMP)
            self.assertEqual(len(self.calls),2)

    def test_unknown_purpose_fails_before_authentication(self):
        with self.assertRaises(BackupStorageError):keys.create_key('id','secret','admin',client_factory=self.factory)
        self.assertEqual(self.calls,[])
