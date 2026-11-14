"""Versioned JSON exports of saved decision data, never authentication records."""
import json
from .workspaces import StorageError, now, WorkspaceState
from .schemas import EvaluationInput, EvaluationOutput

MAX_EXPORT_BYTES = 20_000_000
MAX_WORKSPACES = 1000
MAX_REVIEWS = 5000


def workspace_record(item):
    return {**{key: item[key] for key in ('id','schema_version','revision','created_at','updated_at')},
            'state': WorkspaceState.model_validate(item['state']).model_dump(mode='json')}


def review_record(item):
    # Preserve frozen calculations and versions; never recalculate past reviews.
    return {**{key: item[key] for key in ('id','decision_id','decision_revision','schema_version','created_at')},
            'state': WorkspaceState.model_validate(item['state']).model_dump(mode='json'),
            'evaluation_input': EvaluationInput.model_validate(item['evaluation_input']).model_dump(mode='json'),
            'evaluation': EvaluationOutput.model_validate(item['evaluation']).model_dump(mode='json')}


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def build_export(repo, owner):
    started = now()
    workspaces, reviews = [], []
    size = 0
    revisions = {}
    for item in repo.export_workspaces(owner, MAX_WORKSPACES + 1):
        if len(workspaces) >= MAX_WORKSPACES:
            raise StorageError(413, 'export_too_large', 'This account exceeds the current export limit. No partial file was created.')
        row = workspace_record(item)
        size += len(encode(row))
        if size > MAX_EXPORT_BYTES:
            raise StorageError(413, 'export_too_large', 'This account exceeds the current export size limit. No partial file was created.')
        workspaces.append(row)
        revisions[row['id']] = row['revision']
    for item in repo.export_reviews(owner, started, MAX_REVIEWS + 1):
        if len(reviews) >= MAX_REVIEWS:
            raise StorageError(413, 'export_too_large', 'This account exceeds the current review export limit. No partial file was created.')
        row = review_record(item)
        if row['decision_id'] not in revisions or row['decision_revision'] > revisions[row['decision_id']]:
            raise StorageError(409, 'export_changed', 'Saved data changed while preparing the export. Please try again.')
        size += len(encode(row))
        if size > MAX_EXPORT_BYTES:
            raise StorageError(413, 'export_too_large', 'This account exceeds the current export size limit. No partial file was created.')
        reviews.append(row)
    if revisions != repo.export_revisions(owner, MAX_WORKSPACES + 1):
        raise StorageError(409, 'export_changed', 'Saved workspaces changed while preparing the export. Please try again.')
    result = {
        'format': 'purchase-decision-workspace', 'export_version': 1, 'currency': 'USD',
        'read_started_at': started, 'read_finished_at': now(),
        'consistency': 'per-record read window; workspace revisions checked before completion',
        'scope': 'Saved workspaces and historical reviews. Unsaved tab edits and temporary import previews are excluded.',
        'counts': {'workspaces': len(workspaces), 'historical_reviews': len(reviews)},
        'workspaces': workspaces, 'historical_reviews': reviews,
    }
    content = encode(result)
    if len(content) > MAX_EXPORT_BYTES:
        raise StorageError(413, 'export_too_large', 'This account exceeds the current export size limit. No partial file was created.')
    return content
