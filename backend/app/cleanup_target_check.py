"""Disposable Auth0-only identity test. Read-only unless the exact deletion is confirmed."""
import argparse
import os
from pathlib import Path
from urllib.parse import quote
import httpx
from .auth_provider import provider
from .deletion_provider import delete_identity
from .identity import digest


def inspect_target(subject,expected_email,source,database):
    if not isinstance(subject,str) or not subject.startswith('auth0|') or len(subject)>200:
        return False,'Invalid test-user ID.'
    if not expected_email or '@' not in expected_email or any(c.isspace() for c in expected_email):
        return False,'Enter the exact disposable-user email.'
    profile=source.profile(subject)
    if profile.get('user_id')!=subject or str(profile.get('email','')).casefold()!=expected_email.casefold():
        return False,'The Auth0 user ID and expected test email do not match. No deletion is allowed.'
    owner='user_'+digest(source.config.issuer+'\0'+subject)
    database.command('ping')
    if database['users'].find_one({'$or':[{'subject':subject},{'_id':owner}]},{'_id':1}):
        return False,'This identity has an application account. Refusing the disposable Auth0-only test.'
    for name in ('decisions','snapshots','import_receipts','app_sessions'):
        if database[name].find_one({'owner_id':owner},{'_id':1}):
            return False,'Application records exist for this identity. Refusing the disposable Auth0-only test.'
    if database['deletion_ledger'].find_one({'_id':'account:'+owner},{'_id':1}):
        return False,'A lifecycle record exists for this identity. Use the normal recovery/deletion process.'
    return True,'Test user ID and email match; no account or owned records were found in the configured application database. No deletion was called.'


def verify_missing(subject,source):
    # The existing read-only client verifies the DELETE result without changing users.
    with httpx.Client(timeout=6,follow_redirects=False) as client:
        response=client.get(source.config.issuer+'api/v2/users/'+quote(subject,safe=''),
            headers={'Authorization':'Bearer '+source._token()})
        if response.status_code==404:return True
        response.raise_for_status()
        return False


def run_check(subject,expected_email,source,database,confirm_delete=None):
    if confirm_delete is not None and confirm_delete!=subject:
        return False,'Deletion confirmation does not match the target ID. Nothing was deleted.'
    ok,message=inspect_target(subject,expected_email,source,database)
    if not ok or confirm_delete is None:return ok,message
    cleanup_id=os.environ.get('PDW_AUTH0_DELETION_CLIENT_ID','').strip()
    if not cleanup_id or cleanup_id in (source.config.client_id,source.config.management_id):
        return False,'Configure a separate cleanup client before the deletion test.'
    delete_identity(subject)
    if verify_missing(subject,source):
        return True,'Auth0 accepted deletion of the disposable test user; the read-only verification returned 404 (user absent). No application data or recovery deadlines were changed.'
    return False,'Auth0 accepted the cleanup request, but the user is still visible. Check its status before retrying.'


def main(argv=None):
    from dotenv import load_dotenv
    from pymongo import MongoClient
    load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
    parser=argparse.ArgumentParser(description='Disposable Auth0-only identity check. Deletion requires --confirm-delete with the exact target ID.')
    parser.add_argument('--subject',required=True)
    parser.add_argument('--expected-email',required=True)
    parser.add_argument('--confirm-delete',help='Permanently delete this unused test user; must repeat --subject exactly. Omit for read-only checks.')
    args=parser.parse_args(argv)
    if args.confirm_delete is not None and args.confirm_delete!=args.subject:
        parser.error('--confirm-delete must match --subject exactly')
    try:
        with MongoClient(os.environ.get('PDW_MONGO_URI','mongodb://127.0.0.1:27017'),
                         serverSelectionTimeoutMS=2000,connectTimeoutMS=2000,socketTimeoutMS=5000) as client:
            ok,message=run_check(args.subject,args.expected_email,provider(),
                client[os.environ.get('PDW_MONGO_DATABASE','purchase_decision_workspace')],args.confirm_delete)
    except Exception:
        ok=False
        message=('Cleanup or verification did not complete. Check the disposable user in Auth0 before retrying; the cleanup request may have reached Auth0. No application database writes or maintenance were run.'
            if args.confirm_delete is not None else 'Could not complete the read-only preflight. Check MongoDB, Auth0 read access and the test-user details. No deletion was called.')
    print(message)
    return 0 if ok else 1


if __name__=='__main__':raise SystemExit(main())
