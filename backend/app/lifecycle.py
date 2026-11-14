"""Account lifecycle state machine. Recovery and purge race on one user document."""
import secrets
import time
from .workspaces import StorageError

RECOVERY_SECONDS = 30 * 86400
FRESH_SECONDS = 300


def fresh(record, clock=None):
    stamp=time.time() if clock is None else clock
    if not stamp-FRESH_SECONDS <= record['auth_time'] <= stamp+30:
        raise StorageError(401,'reauth_required','Sign in again before changing account deletion settings.')


def status(user, clock=None):
    stamp=time.time() if clock is None else clock
    pending=user.get('state')=='pending_deletion'
    return {'account_state':user.get('state','active'),
            'delete_after':user.get('delete_after') if pending else None,
            'can_restore':pending and stamp<user.get('delete_after',0),
            'notification_status':user.get('deletion_notice',{}).get('status') if pending else None}


class AccountLifecycle:
    def __init__(self,database):
        self.database=database;self.users=database.users;self.sessions=database.app_sessions
        self.ledger=database.deletion_ledger
        self.users.create_index([('state',1),('delete_after',1)])

    def request(self,user,request_id,clock=None):
        from pymongo import ReturnDocument
        stamp=time.time() if clock is None else clock
        if user['state']=='pending_deletion':
            current=self.users.find_one({'_id':user['_id']})
            if current and current.get('state')=='pending_deletion':return status(current,stamp)
            raise StorageError(409,'account_changed','Your account changed. Check its status again.')
        generation=secrets.token_hex(16)
        row=self.users.find_one_and_update({'_id':user['_id'],'state':'active',
            'lifecycle_version':user.get('lifecycle_version')},
            {'$set':{'state':'pending_deletion','deletion_id':str(request_id),'delete_requested_at':stamp,
                'delete_after':stamp+RECOVERY_SECONDS,'lifecycle_version':generation,
                'deletion_notice':{'id':str(request_id),'status':'queued','attempts':0,'next_attempt':stamp}}},
            return_document=ReturnDocument.AFTER)
        if not row:
            row=self.users.find_one({'_id':user['_id']})
            if not row or row.get('state')!='pending_deletion':
                raise StorageError(409,'account_changed','Your account changed. Sign in and check its status again.')
        # A concurrently created old-generation session is rejected on its next use.
        self.sessions.delete_many({'owner_id':user['_id'],'lifecycle_version':user.get('lifecycle_version')})
        return status(row,stamp)

    def restore(self,user,clock=None):
        from pymongo import ReturnDocument
        stamp=time.time() if clock is None else clock
        row=self.users.find_one_and_update({'_id':user['_id'],'state':'pending_deletion',
            'deletion_id':user.get('deletion_id'),'delete_after':{'$gt':stamp}},
            {'$set':{'state':'active','lifecycle_version':secrets.token_hex(16),'restored_at':stamp,
                     'deletion_notice.status':'cancelled'},
             '$unset':{'delete_after':'','delete_requested_at':'','deletion_id':''}},
            return_document=ReturnDocument.AFTER)
        if not row:
            raise StorageError(409,'recovery_closed','The recovery window ended or the account changed. The account was not restored.')
        self.sessions.delete_many({'owner_id':user['_id'],'lifecycle_version':user.get('lifecycle_version')})
        return {'restored':True,'message':'Deletion cancelled. Your saved workspaces are available again.'}

    def purge_due(self,delete_identity,limit=25,clock=None,progress=None):
        from pymongo import ReturnDocument
        stamp=time.time() if clock is None else clock
        counts={'completed':0,'retry_pending':0}
        candidates=self.users.find({'$or':[{'state':'pending_deletion','delete_after':{'$lte':stamp}},
                                         {'state':'purging'}]}).limit(limit)
        for original in candidates:
            owner=original['_id']
            # Restore succeeds only before this atomic transition and deadline.
            lease=secrets.token_hex(16)
            user=self.users.find_one_and_update({'_id':owner,'deletion_id':original.get('deletion_id'),
                '$or':[{'state':'pending_deletion','delete_after':{'$lte':stamp}},
                        {'state':'purging','$or':[{'purge_lease_until':{'$lte':stamp}},{'purge_lease_until':{'$exists':False}}]}]},
                {'$set':{'state':'purging','purge_lease':lease,'purge_lease_until':stamp+180}},return_document=ReturnDocument.AFTER)
            if not user:continue
            if progress:progress()
            try:
                self.ledger.update_one({'_id':'account:'+owner},{'$setOnInsert':{
                    'kind':'account','owner_id':owner,'delete_after':user['delete_after'],
                    'requested_at':user['delete_requested_at']}},upsert=True)
                for name in ('decisions','snapshots','import_receipts','import_limits','app_sessions'):
                    self.database[name].delete_many({'owner_id':owner})
                # Store this once: retries must not move the backup deadline.
                self.ledger.update_one({'_id':'account:'+owner,'active_purged_at':{'$exists':False}},
                    {'$set':{'active_purged_at':stamp,'backup_removal_due':stamp+RECOVERY_SECONDS}})
                self.users.update_one({'_id':owner,'state':'purging','purge_lease':lease},
                    {'$unset':{'email':'','email_verified':'','deletion_notice':''}})
                delete_identity(user['subject'])
                # Keep only a suppression marker, never an email/provider identity.
                self.users.replace_one({'_id':owner,'state':'purging','deletion_id':user['deletion_id'],'purge_lease':lease},
                    {'_id':owner,'state':'deleted','deleted_at':stamp,'lifecycle_version':secrets.token_hex(16)})
                self.ledger.update_one({'_id':'account:'+owner},{'$set':{'completed_at':stamp}})
                counts['completed']+=1
            except Exception:
                # No raw provider/SMTP errors, subjects, emails, or tokens in output.
                self.users.update_one({'_id':owner,'state':'purging','purge_lease':lease},
                    {'$set':{'purge_lease_until':stamp+60}})
                counts['retry_pending']+=1
            if progress:progress()
        return counts
