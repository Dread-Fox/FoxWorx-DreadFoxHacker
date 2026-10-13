"""Administrator-reviewed argv templates for noninteractive Kali CLIs.

The LLM supplies only typed enum/integer parameters. It cannot supply shell text,
file paths, arbitrary flags, or executable names. This is NOT a sandbox: a CLI
may itself implement redirects, subprocesses, network discovery or plugins.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from .scope import normalize_target
from .jobs import PROFILES

ID = re.compile(r'^[a-z][a-z0-9-]{2,49}$')
TOOL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+-]{0,149}$')
PARAM = re.compile(r'^[a-z][a-z0-9_]{0,24}$')
PLACEHOLDER = re.compile(r'^\{param:([a-z][a-z0-9_]{0,24})\}$')
# Block direct code execution or privilege escalation through the tool name.
REVIEW_ONLY_TOOLS = frozenset('sqlmap masscan nuclei nikto wapiti msfconsole hydra medusa patator ncrack responder bettercap'.split())
INTERPRETERS = frozenset('sh bash zsh fish dash ksh sudo su doas env python python3 python2 perl ruby node php lua java gcc cc make busybox xargs find awk sed socat nc netcat ncat ssh scp rsync curl-wrapper wget'.split())
# An admin may register other CLIs for human-reviewed proposals; autonomous
# delegation is intentionally narrower until a tool-specific risk review is made.
AUTONOMOUS_EXECUTABLES = frozenset('curl nmap dig whois openssl whatweb sslyze ffuf gobuster subfinder httpx-toolkit'.split())
# Prevent attacker-controlled command composition through administrator templates.
# These are guardrails, not a claim of general CLI confinement.
DANGEROUS_FLAGS = frozenset('--script --script-args -e --exec --execute --input-cmd -input-cmd -input-shell --input-shell --proxy --replay-proxy --location -L --follow-redirects --output -o --output-dir --config -config --request -request -X --request-method -H --header --data --data-binary --upload-file -T --insecure -k --disable-sandbox --no-sandbox --privileged --exec-cmd -x'.split())
TOKEN = re.compile(r'^[^\x00-\x1f\x7f]{1,240}$')


def validate_template(document: dict) -> dict:
    if not isinstance(document,dict) or set(document) != {'id','tool','label','hint','target_kind','risk','mode','argv','parameters'}:
        raise ValueError('Template must provide exactly the documented fields')
    aid, tool = document['id'], document['tool']
    if not isinstance(aid,str) or not ID.fullmatch(aid) or aid in PROFILES:
        raise ValueError('Invalid or conflicting adapter ID')
    if not isinstance(tool,str) or not TOOL.fullmatch(tool) or tool in INTERPRETERS:
        raise ValueError('Autonomous command interpreter or invalid executable is prohibited')
    if document['target_kind'] not in ('host','url'):
        raise ValueError('Target must be one approved host or URL')
    if document['risk'] not in ('recon','active','intrusive') or document['mode'] not in ('autonomous','review'):
        raise ValueError('Invalid risk or execution mode')
    if document['mode']=='autonomous' and tool in REVIEW_ONLY_TOOLS:
        raise ValueError('Sensitive scanners and exploitation tools require manual approval')
    if document['risk']=='intrusive' and document['mode']=='autonomous':
        raise ValueError('Intrusive tools always require per-command review')
    if document['mode']=='autonomous' and tool not in AUTONOMOUS_EXECUTABLES:
        raise ValueError('This executable requires per-command review; autonomous adapter support is not approved')
    if any(not isinstance(document[k],str) or not 1<=len(document[k])<=240 for k in ('label','hint')):
        raise ValueError('Missing/oversized label or hint')
    argv=document['argv']; params=document['parameters']
    if not isinstance(argv,list) or not 1<=len(argv)<=36 or any(not isinstance(v,str) or not TOKEN.fullmatch(v) for v in argv):
        raise ValueError('Invalid argv template')
    if argv.count('{target}') != 1:
        raise ValueError('Exactly one explicit target placeholder is required')
    if not isinstance(params,dict) or len(params)>8:
        raise ValueError('Too many parameters')
    for name, schema in params.items():
        if not isinstance(name,str) or not PARAM.fullmatch(name) or not isinstance(schema,dict):
            raise ValueError('Invalid parameter')
        if schema.get('type')=='integer':
            if set(schema)!={'type','min','max','default'} or any(type(schema[k]) is not int for k in ('min','max','default')) or not 0<=schema['min']<=schema['default']<=schema['max']<=300:
                raise ValueError('Invalid bounded integer parameter')
        elif schema.get('type')=='enum':
            choices=schema.get('choices')
            if set(schema)!={'type','choices','default'} or not isinstance(choices,list) or not 1<=len(choices)<=12 or len(set(map(str,choices)))!=len(choices) or not all(isinstance(x,str) and TOKEN.fullmatch(x) for x in choices) or schema['default'] not in choices or any(x in DANGEROUS_FLAGS or x.split('=',1)[0] in DANGEROUS_FLAGS or x.startswith(('/tmp/','/home/','http://','https://')) for x in choices):
                raise ValueError('Invalid enum parameter')
        else:
            raise ValueError('Freeform string arguments are prohibited')
    used=set()
    for value in argv:
        if value == '{target}': continue
        if ((value in DANGEROUS_FLAGS or value.split('=',1)[0] in DANGEROUS_FLAGS) and not (tool=='smbclient' and value=='-L')) or value.startswith(('/tmp/','/home/','/var/tmp/','file://','http://','https://')):
            raise ValueError('Unreviewed redirects, writes, scripts, proxy or writable paths prohibited')
        if value.startswith('-') and ('=' in value or ':' in value):
            # Fixed --key=value is permitted; no dynamic interpolation inside flags.
            if '{' in value or '}' in value: raise ValueError('Placeholders must fill a complete argument')
        matched=PLACEHOLDER.fullmatch(value)
        if matched:
            used.add(matched.group(1))
            if matched.group(1) not in params:
                raise ValueError('Undeclared argument parameter')
        elif '{' in value or '}' in value:
            raise ValueError('Invalid placeholder or shell expansion')
    if used!=set(params):
        raise ValueError('Every parameter must be used exactly as a complete argument')
    return document


def compile_template(document: dict, target: str, parameters: dict | None = None) -> list[str]:
    validate_template(document)
    t=normalize_target(target)
    if ('://' in t) != (document['target_kind']=='url'):
        raise ValueError('This adapter requires a '+document['target_kind']+' target')
    if not isinstance(parameters,dict) or len(parameters)>8:
        raise ValueError('Invalid parameters')
    if set(parameters)-set(document['parameters']):
        raise ValueError('Unapproved parameter supplied')
    values={}
    for name,kind in document['parameters'].items():
        value=parameters.get(name,kind['default'])
        if kind['type']=='integer':
            if type(value) is not int or not kind['min']<=value<=kind['max']:
                raise ValueError('Parameter outside administrator bounds')
            values[name]=str(value)
        else:
            if type(value) is not str or value not in kind['choices']:
                raise ValueError('Parameter is not one of the approved choices')
            values[name]=value
    out=[]
    for token in document['argv']:
        match=PLACEHOLDER.fullmatch(token)
        out.append(t if token=='{target}' else values[match.group(1)] if match else token)
    return out


def validate_library() -> dict:
    path=Path(__file__).with_name('adapter_library.json')
    entries=json.loads(path.read_text())
    if not isinstance(entries,list) or len(entries)>80:
        raise ValueError('Invalid shipped CLI library')
    result={}
    for entry in entries:
        item=validate_template(entry)
        if item['id'] in result: raise ValueError('Duplicate shipped CLI adapter')
        result[item['id']]=item
    return result
