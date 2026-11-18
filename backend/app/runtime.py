"""Explicit deployment boundary. No public fallback to the local demo owner."""
from dataclasses import dataclass
import os
from urllib.parse import urlsplit
import re


@dataclass(frozen=True)
class Runtime:
    hosted: bool = False
    origin: str = 'http://127.0.0.1:5173'
    api_host: str = '127.0.0.1'
    spa_client: str = ''
    audience: str = ''
    testers: frozenset = frozenset()
    base_path: str = '/'

    @property
    def app_url(self):
        return self.origin+self.base_path


def runtime(environ=None):
    env=os.environ if environ is None else environ
    mode = env.get('PDW_RUNTIME', 'local')
    if mode == 'local':
        return Runtime(origin=env.get('PDW_APP_ORIGIN', 'http://127.0.0.1:5173').rstrip('/'))
    if mode != 'staging':
        raise ValueError('PDW_RUNTIME must be local or staging.')
    origin = env.get('PDW_APP_ORIGIN', '')
    # Render assigns this only when creating the service. Use its trusted
    # process environment, never an incoming Host/Forwarded header.
    api = env.get('PDW_API_ORIGIN') or env.get('RENDER_EXTERNAL_URL', '')
    for value in (origin, api):
        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password or url.port
                or url.path or url.query or url.fragment or url.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('Staging requires exact HTTPS origins without paths or ports.')
    testers = frozenset(item.strip().casefold() for item in env.get('PDW_TESTER_EMAILS', '').split(',') if item.strip())
    client = env.get('PDW_AUTH0_SPA_CLIENT_ID', '').strip()
    audience = env.get('PDW_AUTH0_API_AUDIENCE', '').strip()
    base=env.get('PDW_APP_BASE_PATH','/')
    if not re.fullmatch(r'/(?:[a-zA-Z0-9_-]+/)*',base):
        raise ValueError('Use an absolute app base path with a trailing slash.')
    if (env.get('PDW_AUTH_MODE', 'auth0') != 'auth0' or env.get('PDW_LOCAL_STORAGE') == '1'
            or not client or not audience.startswith('https://') or audience==client or not testers or any('@' not in item for item in testers)):
        raise ValueError('Staging requires Auth0, a SPA client/API audience and an explicit tester email allowlist; local storage is forbidden.')
    mongo=env.get('PDW_MONGO_URI','')
    if not mongo.startswith('mongodb+srv://') or not env.get('PDW_MONGO_DATABASE') or any(
            value in mongo.lower() for value in ('tls=false','ssl=false','tlsinsecure=true','tlsallowinvalid')):
        raise ValueError('Staging requires a separate named Atlas database and a TLS-enabled SRV connection.')
    return Runtime(True, origin, urlsplit(api).hostname, client, audience, testers,base)


def check_tester(user):
    from .workspaces import StorageError
    config = runtime()
    if config.hosted and (user.get('email_verified') is not True or str(user.get('email', '')).casefold() not in config.testers):
        raise StorageError(403, 'tester_required', 'This test deployment is limited to approved, verified test accounts.')


def session_token(request):
    if runtime().hosted:
        value = request.headers.get('authorization', '')
        return value[7:] if value.startswith('Bearer ') and 0 < len(value[7:]) <= 256 else None
    return request.cookies.get('pdw_session')
