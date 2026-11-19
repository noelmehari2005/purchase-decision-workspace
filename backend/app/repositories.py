"""Mongo persistence. One bounded working document; unbounded history stays separate."""
from .workspaces import StorageError, now, ensure_candidate_revisions


class MongoRepository:
    def __init__(self, database):
        self.database = database
        self.import_receipts = database.import_receipts
        self.import_limits = database.import_limits
        self.import_receipts.create_index('expires_at', expireAfterSeconds=0)
        self.import_limits.create_index('expires_at', expireAfterSeconds=0)
        self.decisions = database.decisions
        self.snapshots = database.snapshots
        self.decisions.create_index([('owner_id', 1), ('updated_at', -1)])
        self.snapshots.create_index([('owner_id', 1), ('decision_id', 1), ('created_at', -1)])

    @staticmethod
    def clean(document):
        if document is None:
            raise StorageError(404, 'not_found', 'This saved record was not found.')
        if document.get('deleted') is True:
            raise StorageError(404,'not_found','This saved workspace was deleted.')
        return {k: v for k, v in document.items() if k not in ('_id', 'owner_id')}

    def create(self, owner, request_id, state):
        from pymongo.errors import DuplicateKeyError
        self.validate_import_evidence(owner, state)
        stamp = now()
        item = {'_id': f'{owner}:{request_id}', 'owner_id': owner, 'id': str(request_id),
                'schema_version': 1, 'revision': 1, 'created_at': stamp, 'updated_at': stamp, 'state': state}
        try:
            self.decisions.insert_one(item)
            return self.clean(item)
        except DuplicateKeyError:
            existing = self.get(owner, str(request_id))
            # Retry IDs refer to one creation; never overwrite an existing workspace.
            return existing

    def get(self, owner, decision_id):
        return self.clean(self.decisions.find_one({'_id': f'{owner}:{decision_id}', 'owner_id': owner}))

    def list(self, owner, offset, limit):
        docs = self.decisions.find({'owner_id': owner, 'deleted': {'$ne': True}}, {'state.title': 1, 'id': 1, 'revision': 1, 'updated_at': 1}).sort([('updated_at', -1), ('_id', -1)]).skip(offset).limit(limit)
        return [{'id': d['id'], 'title': d['state']['title'], 'revision': d['revision'], 'updated_at': d['updated_at']} for d in docs]

    def update(self, owner, decision_id, expected, state):
        from pymongo import ReturnDocument
        previous = self.get(owner, decision_id)
        if previous['revision'] != expected:
            raise StorageError(409, 'revision_conflict', 'A newer workspace was saved. Open it separately before replacing your local edits.')
        ensure_candidate_revisions(previous['state'], state)
        self.validate_import_evidence(owner, state)
        item = self.decisions.find_one_and_update(
            {'_id': f'{owner}:{decision_id}', 'owner_id': owner, 'revision': expected, 'deleted': {'$ne': True}},
            {'$set': {'state': state, 'updated_at': now()}, '$inc': {'revision': 1}}, return_document=ReturnDocument.AFTER)
        if item is None:
            raise StorageError(409, 'revision_conflict', 'The workspace changed while saving. Your local edits were not overwritten.')
        return self.clean(item)

    def find_snapshot(self, owner, decision_id, snapshot_id):
        self.get(owner,decision_id)
        doc = self.snapshots.find_one({'_id': f'{owner}:{decision_id}:{snapshot_id}', 'owner_id': owner, 'decision_id': decision_id})
        return self.clean(doc) if doc else None

    def save_snapshot(self, owner, snapshot):
        self.get(owner,snapshot['decision_id'])
        from pymongo.errors import DuplicateKeyError
        item = {**snapshot, '_id': f"{owner}:{snapshot['decision_id']}:{snapshot['id']}", 'owner_id': owner}
        try:
            self.snapshots.insert_one(item)
            try:self.get(owner,snapshot['decision_id'])
            except StorageError:
                self.snapshots.delete_one({'_id':item['_id'],'owner_id':owner})
                raise
            return self.clean(item)
        except DuplicateKeyError:
            return self.find_snapshot(owner, snapshot['decision_id'], snapshot['id'])

    def list_snapshots(self, owner, decision_id, offset, limit):
        self.get(owner, decision_id)
        docs = self.snapshots.find({'owner_id': owner, 'decision_id': decision_id},
            {'id': 1, 'decision_revision': 1, 'created_at': 1, 'state.title': 1}).sort([('created_at', -1), ('_id', -1)]).skip(offset).limit(limit)
        return [{'id': d['id'], 'decision_revision': d['decision_revision'], 'created_at': d['created_at'], 'title': d['state']['title']} for d in docs]

    def import_preview(self, owner, request_id):
        from datetime import datetime, timezone
        return self.import_receipts.find_one({'_id': f'{owner}:{request_id}', 'owner_id': owner,
                                             'expires_at': {'$gt': datetime.now(timezone.utc)}})

    def limit_imports(self, owner):
        from datetime import datetime, timedelta, timezone
        from pymongo import ReturnDocument
        stamp = datetime.now(timezone.utc)
        key = f'{owner}:{int(stamp.timestamp()) // 60}'
        item = self.import_limits.find_one_and_update({'_id': key},
            {'$inc': {'count': 1}, '$setOnInsert': {'owner_id': owner, 'expires_at': stamp + timedelta(minutes=2)}},
            upsert=True, return_document=ReturnDocument.AFTER)
        if item['count'] > 10:
            raise StorageError(429, 'import_rate_limit', 'Please wait a minute before importing more products. Your drafts are unchanged.')

    def store_import_preview(self, owner, request_id, identifier, evidence):
        from datetime import datetime, timedelta, timezone
        from pymongo.errors import DuplicateKeyError
        item = {'_id': f'{owner}:{request_id}', 'owner_id': owner, 'identifier': identifier,
                'evidence': evidence, 'expires_at': datetime.now(timezone.utc) + timedelta(days=30)}
        try:
            self.import_receipts.insert_one(item)
            return evidence
        except DuplicateKeyError:
            prior = self.import_preview(owner, request_id)
            if not prior or prior['identifier'] != identifier:
                raise StorageError(409, 'import_request_conflict', 'Start a new product import; this request has expired or changed.')
            return prior['evidence']

    def validate_import_evidence(self, owner, state):
        # A client may correct current values but cannot forge provider originals.
        # Saved copies keep evidence valid after the temporary receipt expires.
        checked = []
        for record in state['records']:
            for laptop in (record['draft'], record['confirmed']):
                evidence = laptop.get('evidence') if laptop else None
                if not evidence or evidence in checked:
                    continue
                receipt = self.import_preview(owner, evidence['receipt_id'])
                valid = receipt and receipt['evidence'] == evidence
                if not valid:
                    path_query = {'$or': [{'state.records.draft.evidence': evidence},
                                          {'state.records.confirmed.evidence': evidence}], 'owner_id': owner}
                    valid = self.decisions.find_one(path_query, {'_id': 1}) is not None
                if not valid:
                    raise StorageError(422, 'invalid_import_evidence', 'This import evidence is unavailable or changed. Import the product again before saving; manual entries remain available.')
                checked.append(evidence)

    def export_workspaces(self, owner, limit):
        return self.decisions.find({'owner_id': owner, 'deleted': {'$ne': True}}).sort('_id', 1).limit(limit).max_time_ms(5000)

    def export_reviews(self, owner, cutoff, limit):
        return self.snapshots.find({'owner_id': owner, 'created_at': {'$lte': cutoff}}).sort('_id', 1).limit(limit).max_time_ms(5000)

    def export_revisions(self, owner, limit):
        rows = self.decisions.find({'owner_id': owner, 'deleted': {'$ne': True}}, {'id': 1, 'revision': 1}).sort('_id', 1).limit(limit).max_time_ms(5000)
        return {row['id']: row['revision'] for row in rows}

    def delete(self, owner, decision_id, expected):
        from pymongo import ReturnDocument
        row=self.decisions.find_one({'_id':f'{owner}:{decision_id}','owner_id':owner})
        if not row:raise StorageError(404,'not_found','This workspace was not found.')
        if row.get('deleted') is not True:
            row=self.decisions.find_one_and_update({'_id':f'{owner}:{decision_id}','owner_id':owner,
                'revision':expected,'deleted':{'$ne':True}},
                {'$set':{'deleted':True,'deleted_at':now()},'$unset':{'state':''}},
                return_document=ReturnDocument.AFTER)
            if not row:raise StorageError(409,'revision_conflict','The workspace changed. Reopen and review it before deleting.')
        self._cleanup_workspace(row)

    def _cleanup_workspace(self, row):
        self.database.deletion_ledger.update_one({'_id':'workspace:'+row['_id']},{'$setOnInsert':{
            'kind':'workspace','owner_id':row['owner_id'],'decision_id':row['id'],'deleted_at':row['deleted_at']}},upsert=True)
        self.snapshots.delete_many({'owner_id':row['owner_id'],'decision_id':row['id']})
        self.decisions.update_one({'_id':row['_id'],'deleted':True},{'$set':{'cleanup_checked_at':now()}})

    def cleanup_deleted_workspaces(self,limit=25,progress=None,should_continue=None):
        count=0
        for row in self.decisions.find({'deleted':True}).sort([('cleanup_checked_at',1),('_id',1)]).limit(limit).max_time_ms(5000):
            if should_continue and not should_continue():break
            if progress:progress()
            self._cleanup_workspace(row);count+=1
        return count
