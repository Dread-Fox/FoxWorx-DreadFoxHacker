"""Optional legacy authentication and token-free operator access, with same-origin CSRF checks."""
from dataclasses import dataclass
from urllib.parse import urlsplit
import asyncio
import hashlib
import hmac
import secrets
import time
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException
from .config import Settings

@dataclass(frozen=True)
class Actor:
    name: str
    expires: int

class Auth:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.jwks = PyJWKClient(cfg.cf_team + '/cdn-cgi/access/certs', cache_jwk_set=True, lifespan=300, timeout=5) if cfg.mode == 'cloudflare' else None
        self.login_attempts: list[float] = []
        self.tickets: dict[str, tuple[str, str, float]] = {}

    def request_origin(self, request) -> str:
        if self.cfg.mode == 'open':
            # The open workbench accepts any tunnel hostname: the operator
            # configures ingress externally. Do not use untrusted forwarded
            # headers for redirects or authentication decisions.
            origin = request.headers.get('origin', '')
            if origin:
                value = urlsplit(origin)
                if (value.scheme in ('http', 'https') and value.netloc and
                        not value.path and not value.query and not value.fragment and
                        not value.username and not value.password):
                    return origin.lower().rstrip('/')
            host = request.headers.get('host', '127.0.0.1:'+str(self.cfg.port))
            return 'http://' + host.lower()
        # Match the exact, administrator-allowlisted Host; never trust Forwarded
        # or X-Forwarded-* as a way to add a public origin.
        host = request.headers.get('host', '').lower()
        for origin in self.cfg.origins:
            if urlsplit(origin).netloc.lower() == host:
                return origin
        raise HTTPException(403, 'Unexpected hostname. Configure FOXWORX_PUBLIC_ORIGIN for HTTPS tunnel access.')

    def is_public_host(self, request) -> bool:
        return self.cfg.public_origin != '' and self.request_origin(request) == self.cfg.public_origin

    def check_host(self, request) -> None:
        if self.cfg.mode == 'open':
            # The service still binds to 127.0.0.1; ingress is intentionally
            # controlled by the operator's own tunnel/reverse proxy.
            return
        requested = self.request_origin(request)
        if self.cfg.mode in ('local', 'proxy'):
            if not request.client or request.client.host not in ('127.0.0.1', '::1'):
                raise HTTPException(403, 'Local mode requires loopback access')
            # Never accept requests proxied onto the insecure localhost hostname.
            # Legitimate HTTPS tunnels must preserve their PUBLIC Host header.
            if (self.cfg.mode == 'local' and requested != self.cfg.public_origin and
                    any(h in request.headers for h in ('cf-connecting-ip', 'cf-ray', 'cf-access-jwt-assertion', 'x-forwarded-for'))):
                raise HTTPException(403, 'Tunnel must preserve its configured public Host header')

    def origin(self, request) -> None:
        if self.cfg.mode == 'open':
            # Require a browser-originated request with a valid web origin;
            # avoid tying this check to the proxy's internal Host header.
            # The explicit CSRF header below prevents cross-site HTML forms.
            origin = request.headers.get('origin', '')
            parsed = urlsplit(origin)
            if (parsed.scheme not in ('https', 'http') or not parsed.netloc or
                    parsed.path or parsed.query or parsed.fragment or
                    parsed.username or parsed.password):
                raise HTTPException(403, 'Browser Origin header required')
            return
        if request.headers.get('origin', '') != self.request_origin(request):
            raise HTTPException(403, 'Origin check failed. Use the same address in the browser.')

    def csrf(self, actor: str) -> str:
        return hmac.new(self.cfg.secret.encode(), ('csrf:' + actor).encode(), hashlib.sha256).hexdigest()

    def mutation(self, request, actor: Actor) -> None:
        self.origin(request)
        if not hmac.compare_digest(request.headers.get('x-foxworx-csrf', ''), self.csrf(actor.name)):
            raise HTTPException(403, 'Session check failed. Reload the page and try again.')

    def verify_cloudflare(self, raw: str) -> Actor:
        if not raw:
            raise HTTPException(401, 'Cloudflare Access login is required')
        try:
            key = self.jwks.get_signing_key_from_jwt(raw)
            claims = jwt.decode(raw, key.key, algorithms=['RS256'], issuer=self.cfg.cf_team,
                                audience=self.cfg.cf_aud, options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']})
            email = str(claims.get('email', '')).lower()
            if not email or email not in self.cfg.emails:
                raise HTTPException(403, 'This identity is not in the workbench email allowlist')
            return Actor(email, int(claims['exp']))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(401, 'Access identity could not be verified. Sign in again; check issuer/AUD if this continues.') from exc

    async def actor(self, request) -> Actor:
        if self.cfg.mode == 'open':
            # Single trusted Linux service account and stable state namespace.
            # No cookies, setup token, Cloudflare identity or login needed.
            return Actor('local-operator', int(time.time())+86400)
        self.check_host(request)
        if self.cfg.mode == 'cloudflare':
            return await asyncio.to_thread(self.verify_cloudflare, request.headers.get('cf-access-jwt-assertion', ''))
        raw = request.cookies.get('foxworx_local', '')
        try:
            data = jwt.decode(raw, self.cfg.secret, algorithms=['HS256'], audience='foxworx-local',
                              options={'require': ['exp', 'sub', 'aud']})
            return Actor(str(data['sub']), int(data['exp']))
        except Exception as exc:
            raise HTTPException(401, 'Local setup login is required') from exc

    def login(self, token: str, remember: bool = False) -> str:
        if self.cfg.mode not in ('local', 'proxy'):
            raise HTTPException(404, 'Token login is disabled')
        t = time.time()
        self.login_attempts = [x for x in self.login_attempts if x > t - 300]
        if len(self.login_attempts) >= 12:
            raise HTTPException(429, 'Too many login attempts. Try again after five minutes.')
        self.login_attempts.append(t)
        if not secrets.compare_digest(token, self.cfg.local_token):
            raise HTTPException(401, 'Incorrect setup token. Run scripts/configure.sh --show-token on the Pi.')
        self.login_attempts.clear()
        return jwt.encode({'sub': 'local-operator', 'aud': 'foxworx-local', 'exp': int(t) + (30 * 86400 if remember else 8 * 3600)}, self.cfg.secret, algorithm='HS256')

    def ticket(self, actor: str, terminal_id: str) -> str:
        self.tickets = {k: v for k, v in self.tickets.items() if v[2] > time.time()}
        if len(self.tickets) >= 100:
            raise HTTPException(429, 'Too many pending terminal connections')
        token = secrets.token_urlsafe(32)
        self.tickets[token] = (actor, terminal_id, time.time() + 30)
        return token

    def consume_ticket(self, token: str, actor: str, terminal_id: str) -> bool:
        value = self.tickets.pop(token, None)
        return bool(value and value[:2] == (actor, terminal_id) and value[2] > time.time())
