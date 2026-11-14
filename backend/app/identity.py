"""Server-owned identity/session records. No passwords or provider tokens stored."""
from datetime import datetime, timezone
from hashlib import sha256
import secrets
import time

from .workspaces import StorageError

IDLE_SECONDS = 3600
ABSOLUTE_SECONDS = 86400


def digest(value):
    return sha256(value.encode()).hexdigest()


def expiration(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc)


def credential_version(value):
    if value is None:
        return None
    try:
        if not isinstance(value,str):raise ValueError('Invalid timestamp')
        changed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if changed.tzinfo is None:raise ValueError('Timezone required')
        return changed.timestamp()
    except (ValueError,TypeError):
        raise StorageError(503,'identity_unavailable','Unable to verify your account right now.')


class IdentityStore:
    def __init__(self, database):
        self.users=database.users
        self.ledger=database.deletion_ledger
        self.sessions=database.app_sessions
        self.flows=database.login_flows
        self.limits=database.auth_limits
        self.sessions.create_index('expires_at',expireAfterSeconds=0)
        self.sessions.create_index('owner_id')
        self.flows.create_index('expires_at',expireAfterSeconds=0)
        self.limits.create_index('expires_at',expireAfterSeconds=0)

    def create_flow(self):
        token=secrets.token_urlsafe(32)
        return token

    def save_flow(self,token,data,clock=None):
        stamp=time.time() if clock is None else clock
        self.flows.replace_one({'_id':digest(token)}, {'_id':digest(token),'data':data,
            'until':stamp+600,'expires_at':expiration(stamp+600)},upsert=True)

    def consume_flow(self,token,clock=None):
        stamp=time.time() if clock is None else clock
        record=self.flows.find_one_and_delete({'_id':digest(token)}) if token else None
        return record['data'] if record and record['until']>stamp else {}

    def create_session(self,issuer,subject,email,verified,auth_time,clock=None,password_changed_at=None):
        stamp=time.time() if clock is None else clock
        version=credential_version(password_changed_at)
        # Auth0 auth_time is whole seconds; password timestamps include fractions.
        # Reject clearly older authentication, then pin the exact credential version
        # so even a subsequent password change within the same second revokes it.
        if version is not None and version>=auth_time+1:
            raise StorageError(401,'fresh_auth_required','Sign in again after changing your password.')
        # Issuer + subject identifies a user. Email is never an ownership/linking key.
        owner='user_'+digest(issuer+'\0'+subject)
        marker=self.ledger.find_one({'_id':'account:'+owner})
        if marker and marker.get('kind')=='account':
            raise StorageError(403,'account_restricted','This account is no longer available.')
        from pymongo.errors import DuplicateKeyError
        try:
            self.users.update_one({'_id':owner,'state':{'$in':['active','pending_deletion']}},
                {'$setOnInsert':{'issuer':issuer,'subject':subject,'state':'active','created_at':stamp},
                 '$set':{'email':email,'email_verified':verified}},upsert=True)
        except DuplicateKeyError as error:
            raise StorageError(403,'account_restricted','This account is no longer available.') from error
        user=self.users.find_one({'_id':owner})
        if user['state'] not in ('active','pending_deletion'):
            raise StorageError(403,'account_restricted','This account cannot access ordinary workspaces.')
        token=secrets.token_urlsafe(32)
        csrf=secrets.token_urlsafe(32)
        self.sessions.insert_one({'_id':digest(token),'owner_id':owner,'created_at':stamp,'auth_time':auth_time,
            'last_active':stamp,'absolute_until':stamp+ABSOLUTE_SECONDS,'csrf':csrf,'credential_version':version,'lifecycle_version':user.get('lifecycle_version'),
            'expires_at':expiration(stamp+ABSOLUTE_SECONDS)})
        return token

    def session(self,token,clock=None,allow_pending=False):
        stamp=time.time() if clock is None else clock
        record=self.sessions.find_one({'_id':digest(token)}) if token else None
        if not record:
            raise StorageError(401,'session_required','Sign in to access your saved workspace.')
        if stamp>=record['absolute_until'] or stamp-record['last_active']>=IDLE_SECONDS:
            self.revoke(token)
            raise StorageError(401,'session_expired','Your session expired. Sign in again to reopen saved work.')
        user=self.users.find_one({'_id':record['owner_id']})
        marker=self.ledger.find_one({'_id':'account:'+record['owner_id']})
        if marker and marker.get('kind')=='account':
            raise StorageError(403,'account_restricted','This account is no longer available.')
        if user and record.get('lifecycle_version')!=user.get('lifecycle_version'):
            self.revoke(token)
            raise StorageError(401,'session_revoked','Sign in again to check your account status.')
        if not user or user['state'] not in (('active','pending_deletion') if allow_pending else ('active',)):
            raise StorageError(403,'account_restricted','This account cannot access ordinary workspaces.')
        return record,user

    def touch(self,token,clock=None):
        stamp=time.time() if clock is None else clock
        # A stale request cannot revive an expired or concurrently revoked session.
        result=self.sessions.update_one({'_id':digest(token),'absolute_until':{'$gt':stamp},
            'last_active':{'$gt':stamp-IDLE_SECONDS}},{'$max':{'last_active':stamp}})
        if result.matched_count!=1:
            raise StorageError(401,'session_expired','Your session expired. Sign in again.')

    def revoke(self,token):
        if token:self.sessions.delete_one({'_id':digest(token)})

    def refresh_profile(self,user,profile,session):
        if profile.get('user_id')!=user['subject'] or profile.get('blocked') is True:
            self.sessions.delete_many({'owner_id':user['_id']})
            raise StorageError(401,'session_revoked','Sign in again to access saved work.')
        version=credential_version(profile.get('last_password_reset'))
        if session.get('credential_version')!=version:
            self.sessions.delete_many({'owner_id':user['_id'],'credential_version':{'$ne':version}})
            raise StorageError(401,'session_revoked','Your password changed. Sign in again to access saved work.')
        verified=profile.get('email_verified') is True
        email=profile.get('email','')
        if not isinstance(email,str) or not email or len(email)>320:
            raise StorageError(503,'identity_unavailable','Unable to verify your account right now.')
        result=self.users.update_one({'_id':user['_id'],'state':{'$in':['active','pending_deletion']},
            'lifecycle_version':session.get('lifecycle_version')},{'$set':{'email_verified':verified,'email':email}})
        if result.matched_count==0:
            raise StorageError(403,'account_restricted','Your account state changed. Sign in again to check its status.')
        return {**user,'email_verified':verified,'email':email}

    def rate_limit(self,key,maximum,seconds,clock=None):
        from pymongo import ReturnDocument
        stamp=time.time() if clock is None else clock
        bucket=int(stamp//seconds)
        key=digest(key)+':'+str(bucket)
        record=self.limits.find_one_and_update({'_id':key},{'$inc':{'count':1},
            '$setOnInsert':{'expires_at':expiration((bucket+2)*seconds)}},upsert=True,return_document=ReturnDocument.AFTER)
        if record['count']>maximum:
            raise StorageError(429,'too_many_requests','Please wait before trying again.')
