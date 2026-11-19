"""Shared, owner-fenced Mongo lease for HTTP and command-line maintenance."""
import secrets
import time
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

LEASE_SECONDS=180


class LeaseLost(RuntimeError):
    pass


class MaintenanceLease:
    def __init__(self,database):
        self.rows=database.maintenance_locks
        self.owner=secrets.token_hex(16)

    def acquire(self):
        stamp=time.time()
        try:
            row=self.rows.find_one_and_update({'_id':'maintenance','$or':[
                {'lease_until':{'$lte':stamp}},{'lease_until':{'$exists':False}}]},
                {'$set':{'owner':self.owner,'lease_until':stamp+LEASE_SECONDS}},
                upsert=True,return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            # Another worker owns the unique _id; never overwrite that lease.
            return False
        return row is not None

    def renew(self):
        stamp=time.time()
        result=self.rows.update_one({'_id':'maintenance','owner':self.owner,'lease_until':{'$gt':stamp}},
            {'$set':{'lease_until':stamp+LEASE_SECONDS}})
        if result.matched_count!=1:
            raise LeaseLost('Maintenance lease is no longer owned.')

    def release(self):
        self.rows.update_one({'_id':'maintenance','owner':self.owner},
            {'$set':{'lease_until':0},'$unset':{'owner':''}})
