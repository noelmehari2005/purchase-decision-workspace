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


def run(database,delete_user=delete_identity,send=None,*,mode='cleanup',limit=25,budget_seconds=35):
    from .notifications import smtp_send
    from .repositories import MongoRepository
    from .identity import expiration
    import time
    from uuid import uuid4
    from .maintenance_lease import MaintenanceLease
    if mode not in ('check','notify','cleanup') or type(limit) is not int or not 1<=limit<=25 or not 1<=budget_seconds<=60:
        raise ValueError('Invalid maintenance bounds or mode.')
    lease=MaintenanceLease(database)
    if not lease.acquire():return {'status':'busy','mode':mode}
    run_id=str(uuid4())
    # Probes/notification-only runs must not make full cleanup look healthy.
    status_id='maintenance' if mode=='cleanup' else 'maintenance_'+mode
    deadline=time.monotonic()+budget_seconds
    within_budget=lambda:time.monotonic()<deadline
    def tick(phase):
        lease.renew()
        database.system_status.update_one({'_id':status_id,'run_id':run_id},
            {'$set':{'heartbeat_at':time.time(),'phase':phase}})
    try:
        database.system_status.update_one({'_id':status_id},{'$set':{'run_id':run_id,'started_at':time.time(),
            'finished_at':None,'heartbeat_at':time.time(),'phase':'starting','status':'running','mode':mode}},upsert=True)
        tick('configuration')
        if mode=='check':
            from .readiness import configuration_report,database_report
            result={'status':'ok','mode':mode,'configuration':configuration_report()['checks'],
                    'database':database_report(database)}
            database.system_status.update_one({'_id':status_id,'run_id':run_id},
                {'$set':{'finished_at':time.time(),'status':'ok'}})
            return result
        repo=MongoRepository(database)
        tick('notifications')
        mail=deliver_pending(database,send or smtp_send,limit=limit,progress=lambda:tick('notifications'),should_continue=within_budget)
        purge={'completed':0,'retry_pending':0};cleaned=0
        if mode=='cleanup':
            tick('account_cleanup')
            purge=AccountLifecycle(database).purge_due(delete_user,limit=limit,progress=lambda:tick('account_cleanup'),should_continue=within_budget)
            tick('workspace_cleanup')
            cleaned=repo.cleanup_deleted_workspaces(limit=limit,progress=lambda:tick('workspace_cleanup'),should_continue=within_budget)
            for collection in ('login_flows','auth_limits'):
                if not within_budget():break
                tick('expired_transients')
                ids=[row['_id'] for row in database[collection].find(
                    {'expires_at':{'$lte':expiration(time.time())}},{'_id':1}).limit(limit).max_time_ms(5000)]
                if ids:database[collection].delete_many({'_id':{'$in':ids}})
        result={'mode':mode,'notifications':mail,'accounts':purge,'workspace_cleanups':cleaned,
                'budget_exhausted':not within_budget()}
        state='retry_pending' if mail['retry_pending'] or purge['retry_pending'] else 'ok'
        if state=='ok' and result['budget_exhausted']:state='partial'
        tick('finished')
        database.system_status.update_one({'_id':status_id,'run_id':run_id},
            {'$set':{'finished_at':time.time(),'status':state}})
        return {'status':state,**result}
    except Exception:
        try:database.system_status.update_one({'_id':status_id,'run_id':run_id},
            {'$set':{'finished_at':time.time(),'status':'failed'}})
        except Exception:pass
        raise
    finally:
        lease.release()



def main():
    parser=argparse.ArgumentParser(description='Process due deletion notices and irreversible deletions.')
    parser.add_argument('--run-once',action='store_true',required=True)
    parser.add_argument('--mode',choices=('check','notify','cleanup'),default='check',help='Start with check; cleanup can irreversibly purge due accounts.')
    args=parser.parse_args()
    try:
        result=run(configured_repository().database,mode=args.mode)
    except Exception:
        print(json.dumps({'status':'failed','message':'Maintenance could not complete. Check database and server configuration.'}))
        raise SystemExit(1) from None
    print(json.dumps(result))
    if result['status'] not in ('ok','busy'):
        raise SystemExit(1)

if __name__=='__main__':main()
