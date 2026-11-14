"""API-only Icecat adapter. User URLs are identifiers, never fetch destinations."""
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, parse_qs, quote, urlunsplit
import httpx
from .import_models import ImportEvidence, SourceField
from .workspaces import StorageError, now

API_URL = 'https://live.icecat.biz/api'
MAX_BYTES = 2_000_000


def identify(request):
    if request.mode == 'mpn':
        return {'Brand': request.brand.strip(), 'ProductCode': request.mpn.strip()}
    value = request.value.strip()
    if request.mode == 'id':
        if not re.fullmatch(r'[1-9]\d{0,11}', value):
            raise StorageError(422, 'invalid_identifier', 'Enter a numeric Icecat product ID.')
        return {'icecat_id': value}
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.hostname not in {'icecat.biz', 'www.icecat.biz'}
                or url.username or url.password or url.port not in (None, 443)):
            raise ValueError()
        # Accept catalogue product URLs and the established product.cgi ID link.
        match = re.search(r'-(\d{1,12})\.html$', url.path)
        if match and '/p/' in url.path:
            return {'icecat_id': match.group(1)}
        params = parse_qs(url.query)
        ids = params.get('product_id', [])
        if url.path in ('/en/p/', '/en/p') and len(ids) == 1 and re.fullmatch(r'[1-9]\d{0,11}', ids[0]):
            return {'icecat_id': ids[0]}
        if url.path == '/en/p.cgi' and len(ids) == 1 and re.fullmatch(r'[1-9]\d{0,11}', ids[0]):
            return {'icecat_id': ids[0]}
    except ValueError:
        pass
    raise StorageError(422, 'unsupported_link', 'Use an Icecat product link, an Icecat ID, or brand and exact part number. Other sites remain manual reference links.')


def fetch_product(identifier, client=None):
    token = os.environ.get('PDW_ICECAT_API_TOKEN', '').strip()
    username = os.environ.get('PDW_ICECAT_USERNAME', '').strip()
    if not token and not username:
        raise StorageError(503, 'import_not_configured', 'Icecat importing needs its server-side username or API token. Manual entry is available.')
    params = {'lang': 'EN', 'content': 'generalinfo,featuregroups', **identifier}
    headers = {'Accept': 'application/json'}
    if token:
        headers['api-token'] = token
    else:
        params['shopname'] = username
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(7, connect=3), follow_redirects=False)
    try:
        import time
        deadline = time.monotonic() + 8
        with client.stream('GET', API_URL, params=params, headers=headers, follow_redirects=False) as response:
            if response.status_code == 429:
                raise StorageError(503, 'import_busy', 'Icecat is limiting requests. Wait before retrying, or enter the missing details manually.')
            if response.is_redirect or response.status_code >= 500:
                raise StorageError(503, 'import_unavailable', 'Icecat is temporarily unavailable. Your laptop details are unchanged.')
            if 'application/json' not in response.headers.get('content-type', ''):
                raise StorageError(503, 'import_unavailable', 'Icecat did not return product data. Try again later or use manual entry.')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                if time.monotonic() > deadline:
                    raise StorageError(503, 'import_unavailable', 'The product request took too long. Retry later or use manual entry.')
                size += len(chunk)
                if size > MAX_BYTES:
                    raise StorageError(503, 'import_unavailable', 'The product response was too large. Use manual entry for this product.')
                chunks.append(chunk)
            import json
            payload = json.loads(b''.join(chunks))
            if not isinstance(payload, dict):
                raise ValueError()
            if response.status_code != 200 or payload.get('msg') != 'OK':
                code = str(payload.get('StatusCode', ''))
                if code in {'8', '16', '17'}:
                    raise StorageError(404, 'product_not_found', 'No matching Icecat data sheet was found. Check the exact part number or enter details manually.')
                if code in {'9', '12', '14', '15'}:
                    raise StorageError(403, 'product_restricted', 'This data sheet is not available through the configured Icecat access. You can still enter its specifications manually.')
                raise StorageError(503, 'import_unavailable', 'Icecat could not provide this product. Check the server configuration or use manual entry.')
            return payload
    except (httpx.HTTPError, ValueError, TypeError) as error:
        raise StorageError(503, 'import_unavailable', 'Icecat could not be reached or returned invalid data. Your current details are unchanged.') from error
    finally:
        if owned:
            client.close()


def text(value, limit=300):
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ''
    return str(value).strip()[:limit]


def convert(raw, unit, kind):
    try:
        if not re.fullmatch(r'\d+(\.\d+)?', raw):
            return ''
        number = Decimal(raw)
        factors = {'capacity': {'GB': 1, 'TB': 1000}, 'weight': {'g': 1, 'kg': 1000}, 'energy': {'Wh': 1}}
        if unit not in factors[kind]:
            return ''
        value = number * factors[kind][unit]
        if not 0 < value <= 10_000_000:
            return ''
        if kind != 'energy' and value != value.to_integral_value():
            return ''
        return format(value.normalize(), 'f')
    except (InvalidOperation, KeyError):
        return ''


def map_product(payload, identifier, receipt_id, reference_link=None):
    data = payload.get('data')
    if not isinstance(data, dict):
        raise StorageError(503, 'import_unavailable', 'Icecat returned incomplete product data. Use manual entry or retry later.')
    general = data.get('GeneralInfo', {})
    if not isinstance(general, dict):
        general = {}
    product_id, brand, mpn = text(general.get('IcecatId'), 12), text(general.get('Brand'), 100), text(general.get('BrandPartCode'), 200)
    if not product_id.isdigit() or not brand or not mpn:
        raise StorageError(422, 'ambiguous_product', 'Icecat did not identify an exact brand and part number. Enter this configuration manually.')
    if (identifier.get('icecat_id', product_id) != product_id or
        ('Brand' in identifier and (identifier['Brand'].casefold() != brand.casefold() or identifier['ProductCode'].casefold() != mpn.casefold()))):
        raise StorageError(422, 'ambiguous_product', 'The returned configuration does not exactly match your request. No specifications were applied.')
    category = general.get('Category', {})
    if not isinstance(category, dict) or str(category.get('CategoryID')) != '151':
        raise StorageError(422, 'unsupported_product', 'This data sheet is not identified as a laptop. This version supports laptops only.')
    fields, issues = [], []
    title = text(general.get('Title'), 200) or f'{brand} {text(general.get("ProductName"), 80) or mpn}'
    fields.extend([SourceField(field='name', raw=title, normalized=title),
                   SourceField(field='configuration', raw=mpn, normalized=f'{brand} · {mpn}'[:300])])
    features = {}
    groups = data.get('FeaturesGroups', [])
    if not isinstance(groups, list):
        groups = []
    for group in groups[:100]:
        if not isinstance(group, dict) or not isinstance(group.get('Features'), list):
            continue
        for feature in group['Features'][:300]:
            if not isinstance(feature, dict) or not isinstance(feature.get('Feature'), dict):
                continue
            features.setdefault(str(feature['Feature'].get('ID')), []).append(feature)
    # General feature IDs, not translated names or category-specific feature IDs.
    for key, fid, kind in [('cpu','47',None), ('os','3233',None), ('ram','11381','capacity'),
                            ('storage','3318','capacity'), ('weight','94','weight'),
                            ('maxRam','1452','capacity'), ('batteryWh','8519','energy')]:
        values = features.get(fid, [])
        if len(values) != 1:
            if len(values) > 1:
                issues.append(f'{key}: multiple source values; left unknown for review.')
            continue
        feature = values[0]
        raw = text(feature.get('RawValue', feature.get('Value', '')), 500)
        measure = feature['Feature'].get('Measure', {})
        unit = text(measure.get('Signs', {}).get('_', ''), 40) if isinstance(measure, dict) and isinstance(measure.get('Signs'), dict) else ''
        normalized = convert(raw, unit, kind) if kind else raw[:300]
        if normalized:
            fields.append(SourceField(field=key, feature_id=fid, raw=raw, unit=unit, normalized=normalized))
        elif raw:
            issues.append(f'{key}: cannot normalize source value {raw[:100]!r} with unit {unit[:40]!r}; left unknown for review.')
    display = features.get('944', [])
    resolution = features.get('1585', [])
    parts, raw_parts = [], []
    for fid, values in [('944', display), ('1585', resolution)]:
        if len(values) == 1:
            f = values[0]
            value = text(f.get('PresentationValue') or f.get('RawValue') or f.get('Value'), 120)
            if value:
                parts.append(value)
                measure = f['Feature'].get('Measure', {})
                sign = text(measure.get('Signs', {}).get('_', ''), 20) if isinstance(measure, dict) and isinstance(measure.get('Signs'), dict) else ''
                raw_parts.append((text(f.get('RawValue', f.get('Value', '')), 120) + ' ' + sign).strip())
    if parts:
        fields.append(SourceField(field='display', feature_id='944/1585', raw=' · '.join(raw_parts), normalized=' · '.join(parts)))
    present = {f.field for f in fields}
    missing = [k for k in ('cpu','os','ram','storage','weight','display') if k not in present]
    if missing:
        issues.append('Not supplied or not safely mapped: ' + ', '.join(missing) + '.')
    issues.append('Seller costs, required-tool compatibility, and battery runtime need separate evidence.')
    source_url = f'https://icecat.biz/en/search?keyword={quote(mpn, safe="")}'
    if reference_link:
        parsed = urlsplit(reference_link)
        if parsed.hostname in {'icecat.biz', 'www.icecat.biz'} and '/p/' in parsed.path and parsed.path.endswith(f'-{product_id}.html'):
            source_url = urlunsplit(('https', parsed.hostname, parsed.path, '', ''))
    if '/search?' in source_url:
        issues.append('The source link searches Icecat by part number. Match the brand and Icecat ID when viewing results.')
    return ImportEvidence(receipt_id=receipt_id, product_id=product_id, brand=brand, mpn=mpn,
        source_url=source_url, retrieved_at=now(), fields=fields, issues=issues)
