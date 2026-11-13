"""Loopback development persistence with Auth0-derived ownership.

The explicit local demonstration mode remains separate from private accounts.
"""
import os
from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from .repositories import MongoRepository
from .workspaces import CreateWorkspace, UpdateWorkspace, CreateSnapshot, StorageError, build_snapshot

router = APIRouter(prefix='/api/v1')
LOCAL_OWNER = 'local-development-user'


@lru_cache(maxsize=1)
def configured_repository():
    from pymongo import MongoClient
    client = MongoClient(os.environ.get('PDW_MONGO_URI', 'mongodb://127.0.0.1:27017'),
                         serverSelectionTimeoutMS=2000, connectTimeoutMS=2000, socketTimeoutMS=5000, tz_aware=True)
    database = client[os.environ.get('PDW_MONGO_DATABASE', 'purchase_decision_workspace')]
    try:return MongoRepository(database)
    except Exception:
        client.close()
        raise


def repository():
    if os.environ.get('PDW_LOCAL_STORAGE') != '1':
        raise StorageError(503, 'storage_disabled', 'Local saved workspaces are not enabled. Your current tab still works.')
    try:
        return configured_repository()
    except Exception as error:
        # No connection string or database/provider details in public errors.
        raise StorageError(503, 'storage_unavailable', 'Cannot reach local storage. Check MongoDB and the backend setup.') from error


def local_owner(request: Request):
    from .auth_api import current_owner
    return current_owner(request)


def safe_operation(action):
    try:
        return action()
    except (StorageError, ValueError):
        raise
    except Exception as error:
        raise StorageError(503, 'storage_unavailable', 'Storage is unavailable. Your local edits are still in this tab; retry when it reconnects.') from error


@router.get('/storage')
def storage_status(owner=Depends(local_owner), repo=Depends(repository)):
    safe_operation(lambda: repo.list(owner, 0, 1))
    from .auth_provider import auth_mode
    return {'mode': 'local-single-user' if auth_mode()=='local' else 'authenticated', 'schema_version': 1}


@router.get('/decisions')
def list_decisions(offset: int = Query(0, ge=0, le=100_000), limit: int = Query(20, ge=1, le=50),
                   owner=Depends(local_owner), repo=Depends(repository)):
    return {'items': safe_operation(lambda: repo.list(owner, offset, limit)), 'offset': offset, 'limit': limit}


@router.post('/decisions', status_code=201)
def create_decision(payload: CreateWorkspace, owner=Depends(local_owner), repo=Depends(repository)):
    return safe_operation(lambda: repo.create(owner, payload.request_id, payload.state.model_dump(mode='json')))


@router.get('/decisions/{decision_id}')
def get_decision(decision_id: UUID, owner=Depends(local_owner), repo=Depends(repository)):
    return safe_operation(lambda: repo.get(owner, str(decision_id)))


@router.patch('/decisions/{decision_id}')
def update_decision(decision_id: UUID, payload: UpdateWorkspace, owner=Depends(local_owner), repo=Depends(repository)):
    return safe_operation(lambda: repo.update(owner, str(decision_id), payload.expected_revision, payload.state.model_dump(mode='json')))


@router.post('/decisions/{decision_id}/snapshots', status_code=201)
def save_snapshot(decision_id: UUID, payload: CreateSnapshot, owner=Depends(local_owner), repo=Depends(repository)):
    def save():
        existing = repo.find_snapshot(owner, str(decision_id), str(payload.request_id))
        if existing:
            return existing
        workspace = repo.get(owner, str(decision_id))
        if workspace['revision'] != payload.expected_revision:
            raise StorageError(409, 'revision_conflict', 'The workspace changed. Save and review the current revision before capturing history.')
        return repo.save_snapshot(owner, build_snapshot(workspace, payload.request_id))
    return safe_operation(save)


@router.get('/decisions/{decision_id}/snapshots')
def snapshots(decision_id: UUID, offset: int = Query(0, ge=0, le=100_000), limit: int = Query(20, ge=1, le=50),
              owner=Depends(local_owner), repo=Depends(repository)):
    return {'items': safe_operation(lambda: repo.list_snapshots(owner, str(decision_id), offset, limit)), 'offset': offset, 'limit': limit}


@router.get('/decisions/{decision_id}/snapshots/{snapshot_id}')
def get_snapshot(decision_id: UUID, snapshot_id: UUID, owner=Depends(local_owner), repo=Depends(repository)):
    item = safe_operation(lambda: repo.find_snapshot(owner, str(decision_id), str(snapshot_id)))
    if item is None:
        raise StorageError(404, 'not_found', 'This saved review was not found.')
    return item


def install_storage(app):
    app.include_router(router)

    @app.exception_handler(StorageError)
    async def storage_error(_request, error):
        return JSONResponse(status_code=error.status, content={'code': error.code, 'message': error.message, 'field_errors': []})

    @app.exception_handler(ValueError)
    async def value_error(_request, _error):
        return JSONResponse(status_code=422, content={'code': 'invalid_workspace',
            'message': 'Review candidate revisions and confirm valid comparison and plan inputs before saving history.', 'field_errors': []})
