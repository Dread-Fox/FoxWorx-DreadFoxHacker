"""Trusted administrator policy for workflows and installed-CLI autonomy.

Schema-1/2 policies authorize reviewed templates. Schema-3 may additionally
permit installed noninteractive executables with agent-constructed arguments.
Absent or untrusted policy disables unattended tool execution.
"""
from __future__ import annotations
import hashlib
import json
import os
import stat
from pathlib import Path
from .jobs import PROFILES
from .command_templates import validate_template, validate_library

POLICY_DEFAULT = Path('/etc/foxworx/adapter-policy.json')
ADAPTERS = {
    name: {**metadata, 'profile': name,
           'risk': 'low-impact reconnaissance',
           'scope': 'input validated; NOT destination-isolated'}
    for name, metadata in PROFILES.items()
}

class PolicyError(ValueError):
    pass


def parse_document(raw: bytes) -> dict:
    if len(raw) > 131072:
        raise PolicyError('Policy exceeds maximum size')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise PolicyError('Invalid policy JSON') from exc
    if not isinstance(data,dict) or type(data.get('schema')) is not int or data['schema'] not in (1,2,3):
        raise PolicyError('Unsupported adapter policy schema')
    expected={'schema','enabled_profiles','max_steps','max_minutes'}
    if data['schema']>=2: expected.add('registered_adapters')
    if data['schema']==3: expected.add('allow_installed_cli')
    if set(data)!=expected:
        raise PolicyError('Unexpected or missing policy fields')
    registered={}
    cli=data.get('allow_installed_cli',False)
    if type(cli) is not bool:raise PolicyError('allow_installed_cli must be a boolean')
    if data['schema']>=2:
        entries=data['registered_adapters']
        if not isinstance(entries,list) or len(entries)>64:
            raise PolicyError('Maximum 64 administrator-registered tools')
        for item in entries:
            try:
                checked=validate_template(item)
            except ValueError as exc:
                raise PolicyError(str(exc)) from exc
            if checked['id'] in registered:
                raise PolicyError('Duplicate registered adapter')
            registered[checked['id']]=checked
    enabled=data['enabled_profiles']
    if not isinstance(enabled,list) or (not enabled and not cli) or len(enabled)>len(ADAPTERS)+len(registered) or any(type(x) is not str for x in enabled):
        raise PolicyError('Specify a nonempty list of approved profiles')
    if len(set(enabled)) != len(enabled) or any(x not in ADAPTERS and x not in registered for x in enabled):
        raise PolicyError('Unknown or duplicate adapter profile')
    steps_cap,minutes_cap=(10000,1440) if data['schema']==3 else (16,30)
    if type(data['max_steps']) is not int or not 1<=data['max_steps']<=steps_cap:
        raise PolicyError(f'Maximum steps must be an integer from 1 to {steps_cap}')
    if type(data['max_minutes']) is not int or not 1<=data['max_minutes']<=minutes_cap:
        raise PolicyError(f'Maximum minutes must be an integer from 1 to {minutes_cap}')
    return {'enabled_profiles':tuple(enabled),'max_steps':data['max_steps'],
            'max_minutes':data['max_minutes'],'registered_adapters':registered,'allow_installed_cli':cli}


class AdapterPolicy:
    def __init__(self, path: Path | str = POLICY_DEFAULT):
        self.path = Path(path)

    def _read_trusted(self) -> bytes:
        p=self.path
        if not p.is_absolute():
            raise PolicyError('Administrator policy path must be absolute')
        # Verify *every* directory in the path is root-owned, and neither
        # group nor other may replace entries. A user-owned directory would
        # allow a service operator to swap the policy for another inode.
        for parent in (p.parent, *p.parent.parents):
            try:
                s=parent.lstat()
            except OSError as exc:
                raise PolicyError('Policy parent directory unavailable') from exc
            if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
                raise PolicyError('Policy parent directory is not trusted')
        try:
            fd=os.open(p,os.O_RDONLY|os.O_CLOEXEC|getattr(os,'O_NOFOLLOW',0))
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PolicyError('Policy file cannot be safely opened') from exc
        try:
            s=os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode & 0o022 or s.st_size>131072:
                raise PolicyError('Policy must be a root-owned, non-writable-by-others regular file')
            raw=os.read(fd,131073)
            if len(raw)>131072:
                raise PolicyError('Policy exceeds maximum size')
            return raw
        finally:
            os.close(fd)

    def current(self) -> dict:
        try:
            raw=self._read_trusted()
            parsed=parse_document(raw)
        except FileNotFoundError:
            return self._disabled('missing')
        except PolicyError:
            return self._disabled('untrusted')
        return {'status':'active','revision':hashlib.sha256(b'foxworx-adapter-v1\0'+raw).hexdigest(),**parsed}

    @staticmethod
    def _disabled(status: str) -> dict:
        return {'status':status,'revision':hashlib.sha256(('disabled:'+status).encode()).hexdigest(),
                'enabled_profiles':(), 'max_steps':0, 'max_minutes':0, 'registered_adapters':{},'allow_installed_cli':False}

    def inventory(self, registry) -> dict:
        state=self.current()
        items={x['name']:x for x in registry.list()}
        builtin=[
            {**meta,'enabled':name in state['enabled_profiles'],
             'installed':bool(items.get(meta['tool'],{}).get('installed')),
             'available':name in state['enabled_profiles'] and bool(items.get(meta['tool'],{}).get('installed')),
             'mode':'autonomous','risk':'recon','parameters':{},'type':'builtin'}
            for name,meta in ADAPTERS.items()]
        added=[]
        for name,entry in state.get('registered_adapters',{}).items():
            installed=bool(items.get(entry['tool'],{}).get('installed'))
            enabled=name in state['enabled_profiles']
            added.append({'profile':name,'label':entry['label'],'tool':entry['tool'],'hint':entry['hint'],
                          'risk':entry['risk'],'mode':entry['mode'],'type':'registered','parameters':entry['parameters'],
                          'enabled':enabled,'installed':installed,
                          'available':enabled and installed and entry['mode']=='autonomous',
                          'review_available':enabled and installed and entry['mode']=='review'})
        return {'status':state['status'],'revision':state['revision'],'allow_installed_cli':state.get('allow_installed_cli',False),
                'profiles':builtin+added,'max_steps':state['max_steps'],'max_minutes':state['max_minutes'],
                'security_note':'Typed command templates are reviewed by an administrator. No shell expansion, but not OS isolation or network egress filtering. Full terminal remains separate and unrestricted.'}


def main(argv=None) -> int:
    """Read-only local policy administration helper. Does not elevate privileges."""
    import argparse
    parser = argparse.ArgumentParser(description='Validate or inspect the administrator adapter policy (no writes)')
    parser.add_argument('action',choices=['validate','check','list'])
    parser.add_argument('path', nargs='?',help='Source policy JSON (validate only)')
    args=parser.parse_args(argv)
    if args.action=='validate':
        if not args.path:
            parser.error('validate requires a path to a JSON file')
        try:
            result=parse_document(Path(args.path).read_bytes())
        except (PolicyError,OSError) as exc:
            print('INVALID: '+str(exc));return 1
        print(f"VALID: {len(result['enabled_profiles'])} authorized adapters, {len(result['registered_adapters'])} registered templates, {result['max_steps']} steps, {result['max_minutes']} minutes")
        return 0
    if args.action=='list':
        for name,metadata in ADAPTERS.items():
            print(f"{name:25} {metadata['tool']:13} {metadata['label']} [built-in]")
        for name,metadata in validate_library().items():
            print(f"{name:25} {metadata['tool']:13} {metadata['label']} [template, {metadata['mode']}]")
        return 0
    state=AdapterPolicy().current()
    print('Administrator adapter policy:',state['status'])
    print('Source: ',POLICY_DEFAULT)
    print('Authorized: ', ', '.join(state['enabled_profiles']) or '(none)')
    print('Run cap: ',state['max_steps'],'steps /',state['max_minutes'],'minutes')
    return 0 if state['status']=='active' else 1

if __name__=='__main__':
    raise SystemExit(main())
