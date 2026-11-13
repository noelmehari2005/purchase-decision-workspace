"""Mongo persistence. One bounded working document; unbounded history stays separate."""
from .workspaces import StorageError, now, ensure_candidate_revisions


class MongoRepository:
    def __init__(self, database):
        self.decisions = database.decisions
        self.snapshots = database.snapshots
        self.decisions.create_index([('owner_id', 1), ('updated_at', -1)])
        self.snapshots.create_index([('owner_id', 1), ('decision_id', 1), ('created_at', -1)])

    @staticmethod
    def clean(document):
        if document is None:
            raise StorageError(404, 'not_found', 'This saved record was not found.')
        return {k: v for k, v in document.items() if k not in ('_id', 'owner_id')}

    def create(self, owner, request_id, state):
        from pymongo.errors import DuplicateKeyError
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
        docs = self.decisions.find({'owner_id': owner}, {'state.title': 1, 'id': 1, 'revision': 1, 'updated_at': 1}).sort([('updated_at', -1), ('_id', -1)]).skip(offset).limit(limit)
        return [{'id': d['id'], 'title': d['state']['title'], 'revision': d['revision'], 'updated_at': d['updated_at']} for d in docs]

    def update(self, owner, decision_id, expected, state):
        from pymongo import ReturnDocument
        previous = self.get(owner, decision_id)
        if previous['revision'] != expected:
            raise StorageError(409, 'revision_conflict', 'A newer workspace was saved. Open it separately before replacing your local edits.')
        ensure_candidate_revisions(previous['state'], state)
        item = self.decisions.find_one_and_update(
            {'_id': f'{owner}:{decision_id}', 'owner_id': owner, 'revision': expected},
            {'$set': {'state': state, 'updated_at': now()}, '$inc': {'revision': 1}}, return_document=ReturnDocument.AFTER)
        if item is None:
            raise StorageError(409, 'revision_conflict', 'The workspace changed while saving. Your local edits were not overwritten.')
        return self.clean(item)

    def find_snapshot(self, owner, decision_id, snapshot_id):
        doc = self.snapshots.find_one({'_id': f'{owner}:{decision_id}:{snapshot_id}', 'owner_id': owner, 'decision_id': decision_id})
        return self.clean(doc) if doc else None

    def save_snapshot(self, owner, snapshot):
        from pymongo.errors import DuplicateKeyError
        item = {**snapshot, '_id': f"{owner}:{snapshot['decision_id']}:{snapshot['id']}", 'owner_id': owner}
        try:
            self.snapshots.insert_one(item)
            return self.clean(item)
        except DuplicateKeyError:
            return self.find_snapshot(owner, snapshot['decision_id'], snapshot['id'])

    def list_snapshots(self, owner, decision_id, offset, limit):
        self.get(owner, decision_id)
        docs = self.snapshots.find({'owner_id': owner, 'decision_id': decision_id},
            {'id': 1, 'decision_revision': 1, 'created_at': 1, 'state.title': 1}).sort([('created_at', -1), ('_id', -1)]).skip(offset).limit(limit)
        return [{'id': d['id'], 'decision_revision': d['decision_revision'], 'created_at': d['created_at'], 'title': d['state']['title']} for d in docs]
