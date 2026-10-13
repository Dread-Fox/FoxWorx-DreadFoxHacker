"""Conservative INPUT scope checks. This is deliberately not an egress firewall."""
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit, unquote


def host(value: str) -> str:
    value = value.rstrip('.').lower()
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        pass
    try:
        value = value.encode('idna').decode('ascii')
    except UnicodeError as exc:
        raise ValueError('Invalid hostname') from exc
    if len(value) > 253 or not value or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', p) for p in value.split('.')):
        raise ValueError('Use one hostname, IP address or HTTP(S) URL; not a command or target list')
    return value


def normalize_target(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError('A target must be a single nonempty host, IP or URL without whitespace')
    if '://' not in value:
        return host(value)
    u = urlsplit(value)
    if u.scheme.lower() not in ('http', 'https') or not u.hostname or u.username or u.password or u.fragment:
        raise ValueError('Only HTTP(S) URLs without credentials or fragments are supported')
    h = host(u.hostname)
    try:
        port = u.port
    except ValueError as exc:
        raise ValueError('Invalid URL port') from exc
    path = u.path or '/'
    decoded = unquote(path)
    if '\\' in decoded or re.search(r'%(?:2f|5c|25)', path, re.I) or any(p in ('.', '..') for p in decoded.split('/')):
        raise ValueError('Ambiguous or traversal paths are not accepted by guided recipes')
    netloc = f'[{h}]' if ':' in h else h
    if port is not None:
        netloc += f':{port}'
    return urlunsplit((u.scheme.lower(), netloc, path, u.query, ''))


def validate_rule(rule: str) -> str:
    rule = rule.strip()
    if rule.startswith('*.'):
        return '*.' + host(rule[2:])
    try:
        return str(ipaddress.ip_network(rule, strict=True)) if '/' in rule and '://' not in rule else normalize_target(rule)
    except ValueError as exc:
        raise ValueError(f'Invalid scope rule: {rule[:120]}') from exc


def _matches(target: str, rule: str) -> bool:
    rule = validate_rule(rule)
    t = urlsplit(target) if '://' in target else None
    th = t.hostname if t else target
    if rule.startswith('*.'):
        return th.endswith('.' + rule[2:]) and th != rule[2:]
    if '://' in rule:
        if not t:
            return False
        r = urlsplit(rule)
        rp, tp = r.port or (443 if r.scheme == 'https' else 80), t.port or (443 if t.scheme == 'https' else 80)
        base = r.path.rstrip('/')
        return (r.scheme == t.scheme and r.hostname == t.hostname and rp == tp
                and (not base or t.path == base or t.path.startswith(base + '/'))
                and (not r.query or t.query == r.query))
    try:
        return ipaddress.ip_address(th) in ipaddress.ip_network(rule, strict=True)
    except ValueError:
        return th == rule


def allowed(target: str, includes: list[str], excludes: list[str]) -> bool:
    try:
        target = normalize_target(target)
        return not any(_matches(target, r) for r in excludes) and any(_matches(target, r) for r in includes)
    except ValueError:
        return False
