"""Conservative, bounded text recognizers. Parse tool output as untrusted observations.

Never assign vulnerability severity, verify a security finding, or execute extracted text.
Only completed zero-exit jobs can produce observation nodes.
"""
from __future__ import annotations
import re

PORT = re.compile(r'^\s*(\d{1,5})/(tcp|udp)\s+open\b', re.I)
HTTP = re.compile(r'^HTTP/(?:1(?:\.\d)?|2|3)(?:\.\d)?\s+(\d{3})\b', re.I)
CURL_STATUS = re.compile(r'^HTTP\s+(\d{3})\s*$', re.I)
TLS = re.compile(r'^\s*Protocol\s*:\s*(TLSv1(?:\.[0123])?)\s*$', re.I)
DNS = re.compile(r'^([^;\s]{1,100})\s+\d{1,8}\s+IN\s+(A|AAAA|CNAME|NS|MX)\s+([^\s]{1,100})\s*$', re.I)


def parse_observations(tool: str, output: str, *, max_items: int = 8) -> list[dict]:
    """Return small evidence-backed claims; never infer exploits or trust free-form narratives."""
    result, seen = [], set()
    name = (tool or '').lower()
    for line in output[:131072].splitlines()[:3000]:
        line = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line).strip()
        label = value = kind = None
        if name in ('nmap','rustscan'):
            match = PORT.match(line)
            if match and 0 < int(match[1]) <= 65535:
                kind='open-port';value=f'{match[1]}/{match[2].lower()}';label=f'{value} open'
        elif name in ('curl','httpx','whatweb'):
            match = HTTP.match(line) or CURL_STATUS.match(line)
            if match:
                kind='http-status';value=match[1];label=f'HTTP {value} reported'
        elif name == 'openssl':
            match=TLS.match(line)
            if match:
                kind='tls-protocol';value=match[1];label=f'{value} reported'
        elif name in ('dig','dnsrecon'):
            match=DNS.match(line)
            if match:
                kind='dns-record';value=f'{match[2].upper()} {match[3]}';label=value[:82]
        if kind and (kind,value) not in seen:
            seen.add((kind,value));result.append({'kind':kind,'value':value[:110],'label':label[:90],
                'confidence':'parsed-unverified','provenance':'Tool output text; independent verification required'})
        if len(result)>=max_items:break
    return result
