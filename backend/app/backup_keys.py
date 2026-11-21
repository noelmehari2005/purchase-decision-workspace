"""Owner-only custom B2 key provisioning; never invoked by the hosted app.

CLI output contains NEW credentials for the owner to save privately. Never run
this CLI through an agent tool or copy its output into chat/logs.
"""
import math
import time

import httpx

from .backup_storage import AUTHORIZE, BUCKET_ID, PREFIX, BackupStorageError, _endpoint, _json, _token

ACCOUNT_ID='d8039099c9c3'
DURATION=90*86400
CAPABILITIES={'writer':['listBuckets','writeFiles'], 'reader':['listBuckets','listFiles','readFiles']}


def create_key(master_id,master_key,kind,*,client_factory=httpx.Client,clock=None):
    """One exact scoped key, one attempt. Caller privately handles returned key."""
    if kind not in CAPABILITIES:
        raise BackupStorageError('Unsupported backup key purpose.')
    _token(master_id);_token(master_key)
    stamp=time.time() if clock is None else clock
    try:
        with client_factory(timeout=httpx.Timeout(30,connect=10),follow_redirects=False,trust_env=False) as client:
            auth=_json(client,'GET',AUTHORIZE,auth=httpx.BasicAuth(master_id,master_key))
            api=auth['apiInfo']['storageApi']
            if auth.get('accountId')!=ACCOUNT_ID or 'writeKeys' not in api['allowed']['capabilities']:
                raise BackupStorageError('B2 account or key-creation permission rejected.')
            requested={'accountId':ACCOUNT_ID,'capabilities':CAPABILITIES[kind],
                       'keyName':'pdw-staging-archive-'+kind,'bucketIds':[BUCKET_ID],
                       'namePrefix':PREFIX,'validDurationInSeconds':DURATION}
            result=_json(client,'POST',_endpoint(api['apiUrl'])+'/b2api/v4/b2_create_key',
                         headers={'Authorization':_token(auth['authorizationToken'])},json=requested)
            expires=result.get('expirationTimestamp')
            if (result.get('accountId')!=ACCOUNT_ID or result.get('bucketIds')!=[BUCKET_ID] or
                    result.get('namePrefix')!=PREFIX or result.get('keyName')!=requested['keyName'] or
                    not isinstance(result.get('capabilities'),list) or
                    set(result['capabilities'])!=set(CAPABILITIES[kind]) or
                    type(expires) not in (int,float) or not math.isfinite(expires) or
                    not stamp*1000<expires<=(stamp+DURATION+300)*1000):
                raise BackupStorageError('Created backup key scope was not confirmed. Inspect B2 before retrying.')
            _token(result['applicationKeyId']);_token(result['applicationKey'])
            return result
    except BackupStorageError:
        raise
    except Exception:
        raise BackupStorageError('Backup key creation not confirmed. Inspect B2 before retrying.') from None


def main():
    import argparse
    import getpass
    import sys
    parser=argparse.ArgumentParser(description='Create exact B2 archive writer and reader keys privately, valid 90 days.')
    parser.add_argument('--create-pair',action='store_true',required=True)
    parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print('Run privately in an interactive Terminal; do not redirect or share this credential output.')
        return 1
    print('Creates two 90-day keys for only this B2 bucket and archives/ prefix.')
    print('Writer: upload only plus scoped bucket listing. Reader: read/list only.')
    print('Neither key can delete files, change bucket settings or create other keys.')
    print('Your master key is used only for B2 authorization/key creation, never saved or printed.')
    print('NEW credentials will be displayed here. Do not copy terminal output into chat or screenshots.')
    try:
        if input('Type CREATE BACKUP KEYS to authorize these grants: ')!='CREATE BACKUP KEYS':
            print('Cancelled; no request made.')
            return 1
        master_id=getpass.getpass('Paste B2 Master keyID (hidden): ')
        master_key=getpass.getpass('Paste its complete Master applicationKey (hidden): ')
        for kind in ('writer','reader'):
            result=create_key(master_id,master_key,kind)
            print('\nSAVE PRIVATELY: '+result['keyName'])
            print('keyID: '+result['applicationKeyId'])
            print('applicationKey: '+result['applicationKey'])
            print('Expires in 90 days; preserve the exact keyID and full applicationKey in your password manager.')
            input('After saving this entry privately, press Return to continue: ')
        print('\nBoth keys created. Report only “Both keys saved”; never share the output above.')
        return 0
    except (EOFError,KeyboardInterrupt):
        print('\nStopped. Some keys may already exist; inspect B2 before running again.')
        return 1
    except Exception:
        print('Key creation not confirmed. Some keys may exist; inspect B2 before retrying. Do not share raw output.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
