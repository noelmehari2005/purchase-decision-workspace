"""Read-only local setup diagnostics; never send mail, import products or purge data."""
import argparse
import json
import os
import re
import time
from email.utils import parseaddr
from pathlib import Path


def check(key,configured,valid=True):
    return {'check':key,'status':'missing' if not configured else 'configured_unverified' if valid else 'invalid'}


def configuration_report(environ=None):
    env=os.environ if environ is None else environ
    value=lambda key:env.get(key,'').strip()
    domain=value('PDW_AUTH0_DOMAIN')
    auth_fields=('PDW_AUTH0_DOMAIN','PDW_AUTH0_CLIENT_ID','PDW_AUTH0_CLIENT_SECRET',
                 'PDW_AUTH0_MANAGEMENT_CLIENT_ID','PDW_AUTH0_MANAGEMENT_CLIENT_SECRET')
    auth_valid=bool(re.fullmatch(r'[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.auth0\.com',domain)) and (value('PDW_APP_ORIGIN') or 'http://127.0.0.1:5173') in ('http://127.0.0.1:5173','http://localhost:5173')
    staging=value('PDW_RUNTIME')=='staging'
    runtime_valid=False
    if staging:
        from .runtime import runtime
        try:runtime(env);runtime_valid=True
        except (ValueError,TypeError):pass
        auth_fields=('PDW_AUTH0_DOMAIN','PDW_AUTH0_SPA_CLIENT_ID','PDW_AUTH0_API_AUDIENCE',
                     'PDW_AUTH0_MANAGEMENT_CLIENT_ID','PDW_AUTH0_MANAGEMENT_CLIENT_SECRET')
        auth_valid=runtime_valid and bool(re.fullmatch(r'[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.auth0\.com',domain))
    host,sender=value('PDW_SMTP_HOST'),value('PDW_SMTP_FROM')
    try:
        port=int(value('PDW_SMTP_PORT') or '465')
        smtp_valid=(1<=port<=65535 and '\n' not in sender and '\r' not in sender and
                    '@' in parseaddr(sender)[1] and bool(value('PDW_SMTP_USERNAME'))==bool(value('PDW_SMTP_PASSWORD')))
    except (ValueError,TypeError):smtp_valid=False
    deletion_id=value('PDW_AUTH0_DELETION_CLIENT_ID')
    deletion_valid=auth_valid and deletion_id not in {value('PDW_AUTH0_MANAGEMENT_CLIENT_ID'),value('PDW_AUTH0_CLIENT_ID'),value('PDW_AUTH0_SPA_CLIENT_ID')}
    checks=[check('private_storage',bool(value('PDW_MONGO_URI')) if staging else value('PDW_LOCAL_STORAGE')=='1',runtime_valid if staging else True),
            check('email_password_auth',all(value(k) for k in auth_fields),auth_valid and value('PDW_AUTH_MODE') in ('','auth0')),
            check('icecat_imports',bool(value('PDW_ICECAT_USERNAME') or value('PDW_ICECAT_API_TOKEN'))),
            check('notification_smtp',bool(host and sender),smtp_valid),
            check('dedicated_auth0_cleanup',bool(deletion_id and value('PDW_AUTH0_DELETION_CLIENT_SECRET')),deletion_valid)]
    return {'format':'pdw-readiness','version':1,'checks':checks,
        'verification':'Configuration presence is not a delivery, provider-permission, coverage or production test.',
        'release_ready':False,'release_blockers':[
            'Hosted HTTPS, cross-origin sign-in and approved-tester access require live verification before release.',
            'Live notification delivery and provider cleanup require separate verification.',
            'Maintenance needs a supervised scheduler with alerts.',
            'Backup expiration, isolated restoration, suppression replay and marker retention are not operationally verified.',
            'Final accessibility, security and usability release evidence remains incomplete.']}


def database_report(database,clock=None):
    stamp=time.time() if clock is None else clock
    database.command('ping')
    record=database.system_status.find_one({'_id':'maintenance'}) or {}
    finished=record.get('finished_at')
    started=record.get('heartbeat_at',record.get('started_at'))
    numeric=lambda item:type(item) in (int,float) and float('-inf')<item<float('inf')
    state='not_observed'
    if record.get('status')=='running':
        state='running' if numeric(started) and 0<=stamp-started<=300 else 'stalled'
    elif numeric(finished):
        state='stale' if not 0<=stamp-finished<=180 else 'ok' if record.get('status')=='ok' else 'retry_or_failure'
    counts={
        'accounts_past_recovery_deadline':database.users.count_documents({'state':'pending_deletion','delete_after':{'$lte':stamp}},maxTimeMS=5000),
        'accounts_awaiting_provider_cleanup':database.users.count_documents({'state':'purging'},maxTimeMS=5000),
        'notices_queued_over_five_minutes':database.users.count_documents({'state':'pending_deletion','delete_requested_at':{'$lte':stamp-300},
            'deletion_notice.status':{'$in':['queued','sending']}},maxTimeMS=5000),
        'backup_deadlines_requiring_verification':database.deletion_ledger.count_documents({'kind':'account','backup_removal_due':{'$lte':stamp}},maxTimeMS=5000),
    }
    return {'status':'reachable','maintenance':state,'counts':counts,
            'attention_required':state not in ('ok','running') or any(counts.values())}


def inspect_database():
    from pymongo import MongoClient
    with MongoClient(os.environ.get('PDW_MONGO_URI','mongodb://127.0.0.1:27017'),
                     serverSelectionTimeoutMS=2000,connectTimeoutMS=2000,socketTimeoutMS=5000) as client:
        return database_report(client[os.environ.get('PDW_MONGO_DATABASE','purchase_decision_workspace')])


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
    parser=argparse.ArgumentParser(description='Read-only setup checks. No notifications, provider requests or deletions.')
    parser.add_argument('--check-database',action='store_true',help='Read database connectivity, job heartbeat and overdue-work counts.')
    args=parser.parse_args()
    report=configuration_report()
    if args.check_database:
        try:report['database']=inspect_database()
        except Exception:report['database']={'status':'unavailable','message':'Check MongoDB and the local server configuration.'}
    print(json.dumps(report,indent=2))
    missing=any(item['status']!='configured_unverified' for item in report['checks'])
    database=report.get('database',{})
    if missing or database.get('status')=='unavailable' or database.get('attention_required'):raise SystemExit(1)

if __name__=='__main__':main()
