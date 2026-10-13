"""Local administration only. No password, package-install or root API is exposed."""
from __future__ import annotations
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import stat
import sys
import tempfile
from dotenv import dotenv_values
from . import __version__
from .config import Settings, DEFAULT_CONFIG, ROOT
from .platforms import host_snapshot, profile_defaults


def write_settings(path: Path, values: dict[str, str]) -> None:
    path = path.expanduser().absolute()
    if path.is_symlink():
        raise ValueError('Refusing a symbolic-link configuration file')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = ['# FOXWORX Workbench v3.3.3. Private configuration; do not publish or send to chat.']
    for key, value in values.items():
        if not key.replace('_', '').isalnum():
            raise ValueError('Invalid configuration key')
        value = str(value or '')
        if '\n' in value or '\r' in value or '\x00' in value:
            raise ValueError(f'{key} must fit on one line')
        lines.append(key + '=' + json.dumps(value, ensure_ascii=True))
    fd, temporary = tempfile.mkstemp(prefix='.settings-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('\n'.join(lines) + '\n')
            stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def initialize(path: Path, *, profile: str = 'auto') -> bool:
    """Create secrets exactly once; an upgrade must not overwrite a working config."""
    path = path.expanduser()
    if path.is_symlink(): raise ValueError('Configuration path must not be a symbolic link')
    if path.exists():
        # Upgrade-only migration: add a stable model-credential encryption key
        # without changing current auth, token, state, or existing provider keys.
        current=dict(dotenv_values(path, interpolate=False))
        if not current.get('FOXWORX_AI_ENCRYPTION_KEY'):
            current['FOXWORX_AI_ENCRYPTION_KEY']=secrets.token_urlsafe(48)
            write_settings(path,current)
        return False
    if profile == 'auto':
        profile=host_snapshot()['profile']
    defaults=profile_defaults(profile)
    write_settings(path, {
        'FOXWORX_AUTH_MODE':'open', 'FOXWORX_PORT':'8765',
        'FOXWORX_ORIGIN':'http://127.0.0.1:8765', 'FOXWORX_PUBLIC_ORIGIN':'',
        'FOXWORX_SESSION_SECRET':secrets.token_urlsafe(48),
        'FOXWORX_LOCAL_TOKEN':'',
        'FOXWORX_AI_ENCRYPTION_KEY':secrets.token_urlsafe(48),
        'FOXWORX_AI_ENDPOINTS':'{}',
        'FOXWORX_STATE':str(Path.home()/'.local/share/foxworx-workbench-v2'),
        'CF_TEAM_DOMAIN':'', 'CF_ACCESS_AUD':'', 'FOXWORX_ALLOWED_EMAILS':'',
        'OPENAI_API_KEY':'', 'OPENAI_MODEL':'',
        'FOXWORX_MAX_JOBS':str(defaults['max_jobs']), 'FOXWORX_JOB_TIMEOUT':'900', 'FOXWORX_LOG_MIB':'5',
        'FOXWORX_MAX_TERMINALS':str(defaults['max_terminals']), 'FOXWORX_RESERVE_MIB':str(defaults['reserve_mib']),
        'FOXWORX_EXTRA_TOOL_PATHS':'', 'FOXWORX_SHELL':'/bin/bash',
    })
    return True


def configure(path: Path, options) -> None:
    created = initialize(path, profile=options.profile)
    if getattr(options, 'local_service', False):
        from .config import Settings
        import shutil
        values = dict(dotenv_values(path, interpolate=False))
        desired = {'FOXWORX_AUTH_MODE':'open', 'FOXWORX_PORT':'8765', 'FOXWORX_ORIGIN':'http://127.0.0.1:8765'}
        # Token-free mode does not need to create or rotate a login token.
        if len(values.get('FOXWORX_SESSION_SECRET') or '') < 32:
            desired['FOXWORX_SESSION_SECRET'] = secrets.token_urlsafe(48)
        if any(values.get(k) != v for k, v in desired.items()):
            backup = path.with_name(path.name + '.before-v3.3.3')
            if not backup.exists():
                shutil.copyfile(path, backup)
                os.chmod(backup, 0o600)
            values.update(desired)
            # Validate before committing; preserve provider credentials, token, secrets and state.
            fd, temporary = tempfile.mkstemp(prefix='.validate-',dir=path.parent)
            os.close(fd)
            try:
                write_settings(Path(temporary),values)
                Settings.load(Path(temporary))
            finally:
                os.unlink(temporary)
            write_settings(path,values)
            print('Configured token-free service on http://127.0.0.1:8765; original configuration backed up.')
        else:
            print('Token-free local service is already configured for http://127.0.0.1:8765.')
        return
    if options.init:
        print(('Created ' if created else 'Preserved ') + str(path))
        return
    if getattr(options, 'public_origin', None) is not None or getattr(options, 'clear_public_origin', False):
        from .config import Settings
        from dataclasses import replace
        values = dict(dotenv_values(path, interpolate=False))
        public = (options.public_origin or '').rstrip('/') if options.public_origin else ''
        # Validate the actual config before touching the file. Never print tokens.
        current = Settings.load(path)
        replace(current,public_origin=public).validate()
        old = values.get('FOXWORX_PUBLIC_ORIGIN','')
        if old != public:
            import shutil
            backup = path.with_name(path.name + '.before-v3.3.3')
            if not backup.exists():
                shutil.copyfile(path,backup)
                os.chmod(backup,0o600)
            values['FOXWORX_PUBLIC_ORIGIN'] = public
            write_settings(path,values)
        print(('Allowed HTTPS browser origin: '+public) if public else 'Optional HTTPS browser origin disabled.')
        print('Local URL: http://127.0.0.1:8765')
        print('Apply changes: systemctl --user restart foxworx-workbench')
        return
    values = dict(dotenv_values(path, interpolate=False))
    if options.show_token:
        if values.get('FOXWORX_AUTH_MODE') not in ('local', 'proxy'):
            raise ValueError('This installation uses token-free access; --show-token applies only to legacy local/proxy login mode')
        print(values.get('FOXWORX_LOCAL_TOKEN', '')); return
    if options.rotate_token:
        values['FOXWORX_LOCAL_TOKEN']=secrets.token_urlsafe(32)
        values['FOXWORX_SESSION_SECRET']=secrets.token_urlsafe(48)
        write_settings(path, values)
        print('Rotated local token and session secret. Restart the service to invalidate local sessions.'); return
    if not sys.stdin.isatty():
        raise ValueError('Interactive configuration needs a terminal. Use --init for unattended local initialization.')
    print('Configure FOXWORX v3.3.3. Enter preserves the displayed value. Secrets are never echoed.')
    def ask(key, description, default=''):
        old=values.get(key) or default
        new=input(f'{description} [{old}]: ').strip()
        values[key]=new or old
    ask('FOXWORX_AUTH_MODE','Authentication: open (no login) / local / proxy / legacy cloudflare','open')
    ask('FOXWORX_PORT','Local listening port','8765')
    if values['FOXWORX_AUTH_MODE']=='proxy':
        print('Optional HTTPS reverse proxy: keep 127.0.0.1 listener and protect the public hostname upstream.')
        ask('FOXWORX_ORIGIN','Exact external HTTPS origin, no path')
    elif values['FOXWORX_AUTH_MODE']=='cloudflare':
        print('Legacy Cloudflare JWT mode is available for existing deployments; it is not required for local service.')
        ask('FOXWORX_ORIGIN','Public HTTPS origin, no trailing path')
        ask('CF_TEAM_DOMAIN','HTTPS team domain, e.g. https://TEAM.cloudflareaccess.com')
        ask('CF_ACCESS_AUD','Access application audience (AUD)')
        ask('FOXWORX_ALLOWED_EMAILS','Permitted operator email addresses, comma separated')
    else:
        values['FOXWORX_ORIGIN']=f'http://127.0.0.1:{values["FOXWORX_PORT"]}'
    print('Each operator can now configure providers, model IDs and encrypted API keys inside the browser.')
    print('Optional: retain a shared OpenAI key configured on this Pi for legacy v2 compatibility.')
    if input('Configure the optional shared OpenAI API key? [y/N]: ').strip().lower()=='y':
        key=getpass.getpass('API key (Enter keeps existing; - clears): ').strip()
        if key: values['OPENAI_API_KEY']='' if key=='-' else key
        ask('OPENAI_MODEL','OpenAI model ID available to your API project')
    print('For remote Ollama / LM Studio / vLLM, edit FOXWORX_AI_ENDPOINTS in settings.env locally.')
    print('Example: {"gpu-ollama":{"provider":"ollama","url":"http://192.168.1.10:11434"}}')
    ask('FOXWORX_EXTRA_TOOL_PATHS','Extra absolute tool directories, colon-separated')
    # Validate without replacing the working file. Settings.load also honors process environment overrides.
    fd, temporary=tempfile.mkstemp(prefix='.validate-',dir=path.parent)
    os.close(fd)
    try:
        write_settings(Path(temporary), values)
        Settings.load(Path(temporary))
    finally:
        os.unlink(temporary)
    write_settings(path,values)
    print('Saved ' + str(path))
    print('Apply changes: systemctl --user restart foxworx-workbench')
    print('The default open mode requires no setup token.')


def vendor_check() -> list[str]:
    manifest=json.loads((ROOT/'static/vendor/manifest.json').read_text())
    errors=[]
    # Manifest file map is deliberately explicit; no network during startup.
    files=manifest.get('files',{})
    if not files:
        return ['manifest has no file hashes']
    if isinstance(files,list):
        files={x['name']:x['sha256'] for x in files}
    for name, expected in files.items():
        if isinstance(expected,dict): expected=expected['sha256']
        p=ROOT/'static/vendor'/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            errors.append(name)
    return errors


def doctor(cfg: Settings) -> int:
    from .registry import Registry
    warnings=[]
    if os.geteuid()==0: warnings.append('Root account: the web service will refuse to start.')
    hardware=host_snapshot(fresh=True)
    if not hardware['supported']: warnings.append('Unsupported host architecture or operating system.')
    warnings.extend(hardware['warnings'])
    if cfg.config_path.exists() and stat.S_IMODE(cfg.config_path.stat().st_mode)&0o077:
        warnings.append('Configuration permissions are too broad; run chmod 600 on the settings file.')
    from .providers import ProviderManager
    from .store import Store
    if not cfg.ai_encryption_key: warnings.append('Dedicated AI encryption key is missing; run configure --init to migrate before saving browser credentials.')
    try:
        from litellm import acompletion
        ai_sdk=True
    except ImportError:
        ai_sdk=False
        warnings.append('LiteLLM is not installed. Install optional requirements-ai.txt for all cloud and local models.')
    if cfg.mode=='open': warnings.append('Token-free mode: everyone who can reach a tunnel hostname can operate the Linux service account. Configure optional ingress controls yourself.')
    elif cfg.mode=='proxy' or cfg.public_origin: warnings.append('Check your independently configured HTTPS proxy and access policy.')
    cfg.state.mkdir(parents=True,exist_ok=True,mode=0o700)
    disk=shutil.disk_usage(cfg.state)
    if disk.free<cfg.reserve_bytes: warnings.append('Free disk space is below the configured reserve; managed jobs will be rejected.')
    from .adapters import AdapterPolicy
    adapter_status=AdapterPolicy(cfg.adapter_policy_path).current()
    if adapter_status['status']!='active':
        warnings.append('Rabbit Hole unattended adapters are disabled until an administrator installs a trusted root-owned policy; see docs/ADAPTER-POLICY.md.')
    reg=Registry(cfg); reg.scan()
    items=reg.list()
    failed_assets=vendor_check()
    if failed_assets: warnings.append('Vendor asset checksum mismatch: '+', '.join(failed_assets))
    output={'version':__version__, 'python':platform.python_version(), 'architecture':hardware['architecture'],
            'hardware':hardware,
            'config':str(cfg.config_path), 'state':str(cfg.state), 'mode':cfg.mode,
            'listening_url':f'http://127.0.0.1:{cfg.port}', 'public_origin':cfg.public_origin,
            'installed_executables':sum(x['installed'] for x in items),
            'curated_installed':sum(x['installed'] and x['curated'] for x in items),
            'curated_total':sum(x['curated'] for x in items), 'free_disk_mib':disk.free//1048576,
            'vendor_checksums':'PASS' if not failed_assets else 'FAIL', 'ai_sdk_installed':ai_sdk,
            'rabbit_adapter_policy':adapter_status['status'],
            'rabbit_enabled_adapters':len(adapter_status['enabled_profiles']),
            'ai_provider_count':len(ProviderManager(cfg, Store(cfg.state)).describe('local-operator')['providers']), 'warnings':warnings,
            'not_checked':['Optional external reverse proxy access', 'API credentials/model access', 'native Kali tool runtime', 'HackerOne authorization']}
    print(json.dumps(output,indent=2))
    return 1 if failed_assets or os.geteuid()==0 or not hardware['supported'] else 0


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description='FOXWORX Kali Workbench v3.3.3 local administration')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('version')
    for name in ('serve','configure','doctor'):
        p=commands.add_parser(name)
        p.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
        if name=='configure':
            p.add_argument('--profile',choices=('auto','pi','workstation'),default='auto',
                           help='Preset only for initial config; never overwrites an existing config')
            group=p.add_mutually_exclusive_group()
            for flag in ('init','show-token','rotate-token','local-service','clear-public-origin'):
                group.add_argument('--'+flag,action='store_true')
            group.add_argument('--public-origin',metavar='HTTPS_URL',
                               help='Allow the exact HTTPS tunnel hostname in addition to localhost')
    args=parser.parse_args(argv)
    try:
        if args.command=='version': print(__version__); return 0
        if args.command=='configure': configure(args.config,args); return 0
        cfg=Settings.load(args.config)
        if args.command=='doctor': return doctor(cfg)
        if not host_snapshot()['supported']:
            raise ValueError('FOXWORX requires native Linux ARM64 or x86-64; run host preflight first')
        if os.geteuid()==0: raise ValueError('Never run this shell-capable service as root. Use a dedicated non-root account.')
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(cfg),host='127.0.0.1',port=cfg.port,workers=1,proxy_headers=False,
                    access_log=False,ws_max_size=65536,ws_max_queue=16,timeout_graceful_shutdown=15)
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print('FOXWORX: '+str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
