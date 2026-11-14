"""Private import previews. Only Save workspace persists working decision inputs."""
from fastapi import APIRouter, Depends
from .storage_api import local_owner, repository, safe_operation
from .workspaces import StorageError
from .import_models import ImportRequest
from .icecat import identify, fetch_product, map_product

router = APIRouter(prefix='/api/v1')

@router.post('/imports/preview')
def preview(payload: ImportRequest, owner=Depends(local_owner), repo=Depends(repository)):
    identifier = identify(payload)
    def run():
        cached = repo.import_preview(owner, str(payload.request_id))
        if cached:
            if cached['identifier'] != identifier:
                raise StorageError(409, 'import_request_conflict', 'Use a new request for a different product.')
            return cached['evidence']
        repo.limit_imports(owner)
        evidence = map_product(fetch_product(identifier), identifier, payload.request_id, payload.value if payload.mode == 'link' else None).model_dump(mode='json')
        return repo.store_import_preview(owner, str(payload.request_id), identifier, evidence)
    return safe_operation(run)
