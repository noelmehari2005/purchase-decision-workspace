"""Separate least-privilege Auth0 client for irreversible provider cleanup."""
import os
from urllib.parse import quote
import httpx
from .auth_provider import settings
from .workspaces import StorageError


def delete_identity(subject):
    config=settings()
    client_id=os.environ.get('PDW_AUTH0_DELETION_CLIENT_ID','').strip()
    secret=os.environ.get('PDW_AUTH0_DELETION_CLIENT_SECRET','').strip()
    if not client_id or not secret:
        raise StorageError(503,'provider_deletion_unconfigured','Configure the dedicated provider deletion client.')
    if not isinstance(subject,str) or not subject.startswith('auth0|') or len(subject)>200:
        raise ValueError('Invalid provider identity')
    with httpx.Client(timeout=6,follow_redirects=False) as client:
        response=client.post(config.issuer+'oauth/token',json={'grant_type':'client_credentials',
            'client_id':client_id,'client_secret':secret,'audience':config.issuer+'api/v2/','scope':'delete:users'})
        response.raise_for_status();token=response.json()['access_token']
        response=client.delete(config.issuer+'api/v2/users/'+quote(subject,safe=''),headers={'Authorization':'Bearer '+token})
        if response.status_code not in (204,404):
            response.raise_for_status()
            raise ValueError('Unexpected provider deletion response')
