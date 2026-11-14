"""Run using a scheduler: python -m backend.app.maintenance --run-once.

No scheduler or backup-deletion guarantee is implied by this local command.
"""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
from .storage_api import configured_repository
from .lifecycle import AccountLifecycle
from .notifications import deliver_pending
from .deletion_provider import delete_identity


def run(database,delete_user=delete_identity,send=None):
    from .notifications import smtp_send
    from .repositories import MongoRepository
    from .identity import expiration
    import time
    repo=MongoRepository(database)
    mail=deliver_pending(database,send or smtp_send)
    purge=AccountLifecycle(database).purge_due(delete_user)
    cleaned=repo.cleanup_deleted_workspaces()
    for collection in ('login_flows','auth_limits'):
        database[collection].delete_many({'expires_at':{'$lte':expiration(time.time())}})
    return {'notifications':mail,'accounts':purge,'workspace_cleanups':cleaned}


def main():
    parser=argparse.ArgumentParser(description='Process due deletion notices and irreversible deletions.')
    parser.add_argument('--run-once',action='store_true',required=True)
    parser.parse_args()
    try:
        result=run(configured_repository().database)
    except Exception:
        print(json.dumps({'status':'failed','message':'Maintenance could not complete. Check database and server configuration.'}))
        raise SystemExit(1) from None
    print(json.dumps(result))
    if result['notifications']['retry_pending'] or result['accounts']['retry_pending']:
        raise SystemExit(1)

if __name__=='__main__':main()
