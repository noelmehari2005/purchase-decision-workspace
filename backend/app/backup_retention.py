"""Read-only expiration evidence for one known disposable fictional probe."""
import httpx

from .backup_recovery import authorize_reader
from .backup_storage import BUCKET_ID, BackupStorageError, _endpoint, _json

# Original 311-byte fictional transport probe; never the real staging archive.
PROBE='archives/3b4fe0d6dbc647c189690f3cb6c60327.pdwbackup'


def check_probe(key_id,application_key,*,client_factory=httpx.Client):
    try:
        with client_factory(timeout=httpx.Timeout(30,connect=10),follow_redirects=False,trust_env=False) as client:
            auth,storage=authorize_reader(client,key_id,application_key)
            result=_json(client,'POST',_endpoint(storage['apiUrl'])+'/b2api/v4/b2_list_file_versions',
                         headers={'Authorization':auth['authorizationToken']},
                         json={'bucketId':BUCKET_ID,'prefix':PROBE,'maxFileCount':100})
            files=result.get('files')
            if (not isinstance(files,list) or len(files)>100 or result.get('nextFileName') is not None or
                    result.get('nextFileId') is not None or
                    any(not isinstance(row,dict) or row.get('fileName')!=PROBE or
                        row.get('action') not in ('upload','hide') for row in files)):
                raise BackupStorageError('Complete probe version listing was not confirmed.')
            return {'probe':PROBE,'probe_versions_present':len(files),
                    'uploaded_versions_present':sum(row['action']=='upload' for row in files),
                    'hide_markers_present':sum(row['action']=='hide' for row in files),
                    'probe_expiry_verified':not files,'real_archive_expiry_verified':False,
                    'deletion_requested_by_command':False}
    except BackupStorageError:
        raise
    except Exception:
        raise BackupStorageError('Probe retention check failed.') from None


def main():
    import argparse
    import getpass
    import json
    import sys
    parser=argparse.ArgumentParser(description='Read-only B2 version check for the known disposable expiry probe.')
    parser.add_argument('--check-probe',action='store_true',required=True)
    parser.parse_args()
    if not sys.stdin.isatty():
        print('Run interactively with hidden reader credentials.');return 1
    try:
        key_id=getpass.getpass('B2 READER keyID (hidden): ')
        app_key=getpass.getpass('B2 READER applicationKey (hidden): ')
        print(json.dumps(check_probe(key_id,app_key)))
        return 0
    except (Exception,KeyboardInterrupt):
        print('Probe retention check not confirmed. No files were changed or deleted.');return 1


if __name__=='__main__':
    raise SystemExit(main())
