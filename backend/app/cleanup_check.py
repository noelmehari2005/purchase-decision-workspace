"""Verify cleanup-client credentials without calling user APIs or maintenance."""
import os
from pathlib import Path
import httpx
from .auth_provider import settings


def check_access():
    config=settings()
    client_id=os.environ.get('PDW_AUTH0_DELETION_CLIENT_ID','').strip()
    secret=os.environ.get('PDW_AUTH0_DELETION_CLIENT_SECRET','').strip()
    if not client_id or not secret or client_id in (config.client_id,config.management_id):
        return False,'Configure a separate cleanup client and its secret.'
    with httpx.Client(timeout=6,follow_redirects=False) as client:
        response=client.post(config.issuer+'oauth/token',json={
            'grant_type':'client_credentials','client_id':client_id,'client_secret':secret,
            'audience':config.issuer+'api/v2/','scope':'delete:users'})
        response.raise_for_status()
        body=response.json()
    if not isinstance(body.get('access_token'),str) or not body['access_token']:
        return False,'Auth0 did not return a usable access token.'
    scopes=body.get('scope','')
    if not isinstance(scopes,str) or set(scopes.split())!={'delete:users'}:
        return False,'Auth0 issued a token, but its response did not confirm only delete:users. Review the cleanup grant in Auth0.'
    return True,'Auth0 accepted the cleanup credentials and returned delete:users. No user API or deletion was called.'


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
    try:
        ok,message=check_access()
    except httpx.HTTPStatusError as error:
        ok=False;message=f'Auth0 rejected the token request (HTTP {error.response.status_code}). Check the cleanup client, secret and API grant.'
    except httpx.RequestError:
        ok=False;message='Could not reach Auth0. Check the network and tenant configuration.'
    except Exception:
        ok=False;message='Could not verify cleanup access. Check the local configuration.'
    # Never print a token, credentials, identities or provider response body.
    print(message)
    return 0 if ok else 1


if __name__=='__main__':raise SystemExit(main())
