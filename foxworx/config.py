"""Configuration is explicit and fail-closed; secrets never go to the browser."""
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
import os
import json
import re
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path.home() / '.config/foxworx-workbench/settings.env'
SAFE_PATH = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

@dataclass
class Settings:
    state: Path
    secret: str
    local_token: str
    mode: str = 'open'
    port: int = 8765
    origin: str = 'http://127.0.0.1:8765'
    public_origin: str = ''  # Optional explicitly approved HTTPS tunnel hostname.
    cf_team: str = ''
    cf_aud: str = ''
    emails: tuple[str, ...] = ()
    api_key: str = ''
    model: str = ''
    anthropic_api_key: str = ''
    gemini_api_key: str = ''
    xai_api_key: str = ''
    deepseek_api_key: str = ''
    mistral_api_key: str = ''
    ai_endpoints: dict = field(default_factory=dict)
    ai_encryption_key: str = ''
    max_jobs: int = 2
    job_timeout: int = 900
    log_bytes: int = 5 * 1024 * 1024
    max_terminals: int = 4
    reserve_bytes: int = 256 * 1024 * 1024
    extra_paths: tuple[str, ...] = ()
    shell: str = '/bin/bash'
    config_path: Path = field(default_factory=lambda: DEFAULT_CONFIG)
    adapter_policy_path: Path = Path('/etc/foxworx/adapter-policy.json')
    docs_online: bool = False
    docs_search_key: str = ''
    discord_bot_token: str = ''
    discord_channel_id: str = ''
    discord_guild_id: str = ''
    discord_poll_seconds: int = 30
    discord_node_label: str = 'FOXWORX'

    def validate(self) -> None:
        if bool(self.discord_bot_token) != bool(self.discord_channel_id):
            raise ValueError('Discord bot token and channel ID must be provided together')
        if self.discord_channel_id and not re.fullmatch(r'[0-9]{15,22}', self.discord_channel_id):
            raise ValueError('Discord channel ID must be a numeric snowflake')
        if self.discord_guild_id and not re.fullmatch(r'[0-9]{15,22}', self.discord_guild_id):
            raise ValueError('Discord guild ID must be a numeric snowflake')
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9 _-]{0,39}', self.discord_node_label):
            raise ValueError('Discord node label must be 1–40 safe printable characters')
        if not 15 <= self.discord_poll_seconds <= 300:
            raise ValueError('Discord polling must be 15–300 seconds')
        if self.mode not in ('open', 'local', 'proxy', 'cloudflare'):
            raise ValueError('FOXWORX_AUTH_MODE must be open, local, proxy, or legacy cloudflare')
        if self.ai_encryption_key and len(self.ai_encryption_key) < 40:
            raise ValueError('FOXWORX_AI_ENCRYPTION_KEY must be at least 40 characters')
        if len(self.secret) < 32:
            raise ValueError('Run scripts/configure.sh: a session secret of at least 32 characters is required')
        if self.mode == 'local' and len(self.local_token) < 32:
            raise ValueError('Run scripts/configure.sh: a local setup token of at least 32 characters is required')
        if not 1024 <= self.port <= 65535:
            raise ValueError('FOXWORX_PORT must be between 1024 and 65535')
        if self.mode == 'cloudflare':
            if not re.fullmatch(r'https://[a-zA-Z0-9-]+\.cloudflareaccess\.com', self.cf_team):
                raise ValueError('CF_TEAM_DOMAIN must be your HTTPS cloudflareaccess.com team domain')
            if not self.cf_aud or not self.emails:
                raise ValueError('Legacy Cloudflare mode requires CF_ACCESS_AUD and FOXWORX_ALLOWED_EMAILS')
        if self.public_origin:
            # An external hostname is always opt-in, and never disables local login.
            u = urlsplit(self.public_origin)
            if (self.mode not in ('local', 'open') or u.scheme != 'https' or not u.hostname or
                    not re.fullmatch(r'[a-zA-Z0-9.-]+', u.hostname) or
                    u.hostname in ('localhost', '127.0.0.1', '::1') or
                    u.username or u.password or u.path or u.query or u.fragment or
                    not u.netloc or not (u.port is None or 1 <= u.port <= 65535)):
                raise ValueError('FOXWORX_PUBLIC_ORIGIN must be an exact public HTTPS origin and requires local mode')
        if self.mode in ('proxy', 'cloudflare'):
            u = urlsplit(self.origin)
            if (u.scheme != 'https' or not u.hostname or u.path or u.query or u.fragment or
                    u.username or u.password or not u.netloc or not (u.port is None or 1 <= u.port <= 65535)):
                raise ValueError('Proxy origin must be the exact public HTTPS origin, without a path')
        if not 1 <= self.max_jobs <= 8 or not 1 <= self.max_terminals <= 12:
            raise ValueError('Job/session limits are outside the supported range')
        if not 5 <= self.job_timeout <= 86400 or not 1024 <= self.log_bytes <= 100 * 1024 * 1024:
            raise ValueError('Timeout or log-size limit is outside the supported range')
        if not Path(self.shell).is_file() or not os.access(self.shell, os.X_OK):
            raise ValueError('FOXWORX_SHELL must name an installed executable shell')
        from .providers import ProviderManager, approved_endpoint_url, PROVIDERS
        for name, item in self.ai_endpoints.items():
            if not isinstance(item, dict) or item.get('provider') not in PROVIDERS or PROVIDERS[item['provider']]['cloud']:
                raise ValueError('FOXWORX_AI_ENDPOINTS must specify supported self-hosted providers')
            approved_endpoint_url(item.get('url', ''))
        for p in self.extra_paths:
            if not Path(p).is_absolute():
                raise ValueError('Extra tool paths must be absolute')

    @property
    def origins(self) -> set[str]:
        if self.mode in ('proxy', 'cloudflare'):
            return {self.origin}
        return {f'http://127.0.0.1:{self.port}', f'http://localhost:{self.port}', f'http://[::1]:{self.port}'} | ({self.public_origin} if self.public_origin else set())

    @property
    def tool_path(self) -> str:
        return SAFE_PATH + (':' + ':'.join(self.extra_paths) if self.extra_paths else '')

    @classmethod
    def load(cls, path: Path | None = None) -> 'Settings':
        path = path or Path(os.getenv('FOXWORX_CONFIG', str(DEFAULT_CONFIG)))
        data = {**dotenv_values(path, interpolate=False), **os.environ}
        val = lambda k, default='': str(data.get(k) or default).strip()
        cfg = cls(
            state=Path(val('FOXWORX_STATE', str(Path.home() / '.local/share/foxworx-workbench-v2'))).expanduser(),
            secret=val('FOXWORX_SESSION_SECRET'), local_token=val('FOXWORX_LOCAL_TOKEN'),
            mode=val('FOXWORX_AUTH_MODE', 'open'), port=int(val('FOXWORX_PORT', '8765')),
            origin=val('FOXWORX_ORIGIN', 'http://127.0.0.1:8765').rstrip('/'),
            public_origin=val('FOXWORX_PUBLIC_ORIGIN').rstrip('/'),
            cf_team=val('CF_TEAM_DOMAIN').rstrip('/'), cf_aud=val('CF_ACCESS_AUD'),
            emails=tuple(x.strip().lower() for x in val('FOXWORX_ALLOWED_EMAILS').split(',') if x.strip()),
            api_key=val('OPENAI_API_KEY'), model=val('OPENAI_MODEL'),
            anthropic_api_key=val('ANTHROPIC_API_KEY'), gemini_api_key=val('GEMINI_API_KEY'),
            xai_api_key=val('XAI_API_KEY'), deepseek_api_key=val('DEEPSEEK_API_KEY'),
            mistral_api_key=val('MISTRAL_API_KEY'),
            ai_endpoints=json.loads(val('FOXWORX_AI_ENDPOINTS','{}')),
            ai_encryption_key=val('FOXWORX_AI_ENCRYPTION_KEY'),
            max_jobs=int(val('FOXWORX_MAX_JOBS', '2')), job_timeout=int(val('FOXWORX_JOB_TIMEOUT', '900')),
            log_bytes=int(val('FOXWORX_LOG_MIB', '5')) * 1024 * 1024,
            max_terminals=int(val('FOXWORX_MAX_TERMINALS', '4')),
            reserve_bytes=int(val('FOXWORX_RESERVE_MIB', '256')) * 1024 * 1024,
            extra_paths=tuple(x for x in val('FOXWORX_EXTRA_TOOL_PATHS').split(':') if x),
            shell=val('FOXWORX_SHELL', '/bin/bash'), config_path=path,
            adapter_policy_path=Path(val('FOXWORX_ADAPTER_POLICY','/etc/foxworx/adapter-policy.json')),
            docs_online=val('FOXWORX_DOCS_ONLINE','false').lower() in ('true','1','yes'),
            docs_search_key=val('FOXWORX_DOCS_SEARCH_KEY'),
            discord_bot_token=val('FOXWORX_DISCORD_BOT_TOKEN'),
            discord_channel_id=val('FOXWORX_DISCORD_CHANNEL_ID'),
            discord_guild_id=val('FOXWORX_DISCORD_GUILD_ID'),
            discord_poll_seconds=int(val('FOXWORX_DISCORD_POLL_SECONDS','30')),
            discord_node_label=val('FOXWORX_DISCORD_NODE_LABEL','FOXWORX'),
        )
        cfg.validate()
        return cfg


def child_environment(cfg: Settings) -> dict[str, str]:
    """Do not inherit API keys, Access tokens, proxy configuration or Python hooks."""
    import pwd
    user = pwd.getpwuid(os.getuid())
    return {'PATH': cfg.tool_path, 'HOME': user.pw_dir, 'USER': user.pw_name,
            'LOGNAME': user.pw_name, 'SHELL': cfg.shell, 'TERM': 'xterm-256color',
            'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'COLORTERM': 'truecolor'}
