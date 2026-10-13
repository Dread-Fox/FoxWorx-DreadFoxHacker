"""Read-only Linux hardware inventory and conservative interface role management.

Sources are bounded sysfs/procfs reads; never runs lspci/lsusb with elevated
privileges, toggles radios, opens block devices, or changes routing.  A
reported capability is descriptive, not a grant of device permissions.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from fastapi import HTTPException

IFNAME = re.compile(r'^[A-Za-z0-9_.-]{1,15}$')
MAX_DEVICES = 256
SAFE_TEXT = re.compile(r'[^\x20-\x7E]')
ROLE_SET = frozenset({'management', 'assessment', 'reserved'})


def _read(path: Path, max_bytes: int = 256) -> str:
    try:
        with path.open('rb') as f:
            return SAFE_TEXT.sub('', f.read(max_bytes).decode('utf-8', 'replace').strip())[:max_bytes]
    except (OSError, UnicodeError, ValueError):
        return ''


def _entries(path: Path, limit: int = MAX_DEVICES) -> list[Path]:
    try:
        return sorted((e for e in path.iterdir() if not e.name.startswith('.')), key=lambda p:p.name)[:limit]
    except (OSError, ValueError):
        return []


def _natural(value: str, default: int = 0) -> int:
    try:
        return max(0, int(value.strip(), 10))
    except ValueError:
        return default


def _default_interfaces(proc: Path) -> set[str]:
    """Identify default egress routes without probes, socket opens or DNS."""
    result=set()
    try:
        rows=(proc/'net/route').read_text(errors='replace').splitlines()[1:512]
        for row in rows:
            fields=row.split()
            if len(fields)>3 and fields[1]=='00000000' and int(fields[3],16)&1 and IFNAME.fullmatch(fields[0]):
                result.add(fields[0])
    except (OSError,ValueError):
        pass
    try:
        for row in (proc/'net/ipv6_route').read_text(errors='replace').splitlines()[:512]:
            fields=row.split()
            if len(fields)>=10 and fields[0]=='0'*32 and fields[1]=='00' and IFNAME.fullmatch(fields[-1]):
                result.add(fields[-1])
    except (OSError,ValueError):
        pass
    return result


def _monitor_support(phy: str, iw: str | None) -> str:
    if not iw or not re.fullmatch(r'phy[0-9]{1,4}', phy):
        return 'unknown'
    try:
        reply=subprocess.run([iw,'phy',phy,'info'],capture_output=True,text=True,
                             timeout=2,check=False,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
        if reply.returncode:
            return 'unknown'
        section=reply.stdout[:65536].split('Supported interface modes:',1)
        if len(section)<2: return 'unknown'
        modes=section[1].split('\n\tBand ',1)[0]
        # Limit matching to indented mode lines, not arbitrary user supplied text.
        return 'supported' if re.search(r'^\s*\* monitor\s*$',modes,re.M) else 'not-listed'
    except (OSError,subprocess.TimeoutExpired):
        return 'unknown'


def _identity(sysclass: Path, name: str) -> str:
    """Nonreversible fingerprint used to invalidate stale saved roles."""
    base=sysclass/'net'/name
    try:
        device=str((base/'device').resolve(strict=True))
    except (OSError,RuntimeError):
        device='virtual:'+name
    # Deliberately do not expose interface MAC or hardware serial to web clients.
    address=_read(base/'address',48)
    return hashlib.sha256((name+'\0'+device+'\0'+address).encode()).hexdigest()[:24]


def discover(sysroot: Path = Path('/sys'), procroot: Path = Path('/proc'), *, iw: str | None = None) -> dict:
    """Inventory the *visible* Linux hardware tree without modifying devices.

    An unexposed/unsupported device cannot be discovered; device class labels
    are best-effort, and wireless injection is always unknown absent an
    explicit authorized functional test.
    """
    root=Path(sysroot); cls=root/'class'; bus=root/'bus'
    iw=shutil.which('iw') if iw is None else iw
    defaults=_default_interfaces(Path(procroot))
    wireless=[]; networks=[]
    for item in _entries(cls/'net',64):
        name=item.name
        if not IFNAME.fullmatch(name): continue
        kind='wireless' if (item/'wireless').exists() or (item/'phy80211').exists() else 'ethernet-or-virtual'
        phy=''
        if kind=='wireless':
            try:
                phy=(item/'phy80211').resolve().name
            except (OSError,RuntimeError): pass
        driver=''
        try: driver=(item/'device/driver').resolve(strict=True).name[:60]
        except (OSError,RuntimeError): pass
        is_virtual=not (item/'device').exists()
        kind='virtual' if is_virtual and kind!='wireless' else kind
        link=_read(item/'operstate',30) or 'unknown'
        row={'name':name,'type':kind,'state':link,'ifindex':_natural(_read(item/'ifindex',15)),
             'mtu':_natural(_read(item/'mtu',15)), 'driver':driver,
             'wireless_phy':phy, 'monitor_mode':_monitor_support(phy,iw) if phy else 'unknown',
             'packet_injection':'unverified', 'default_route':name in defaults,
             'protected':name in defaults or name=='lo',
             'identity':_identity(cls,name)}
        networks.append(row)
        if kind=='wireless': wireless.append(name)
    pci=[]; gpu_bus=[]; accelerator_candidates=[]
    for item in _entries(bus/'pci/devices',256):
        clsid=_read(item/'class',16); vendor=_read(item/'vendor',16); did=_read(item/'device',16)
        if not clsid or not vendor: continue
        category=('display' if clsid.lower().startswith('0x03') else
                  'network' if clsid.lower().startswith('0x02') else
                  'processing-accelerator-candidate' if clsid.lower().startswith('0x12') else
                  'storage' if clsid.lower().startswith('0x01') else 'other')
        row={'slot':item.name[:36],'class':clsid,'vendor_id':vendor,'device_id':did,'category':category,
             'driver':'','numa_node':_read(item/'numa_node',8)}
        try:row['driver']=(item/'driver').resolve(strict=True).name[:60]
        except (OSError,RuntimeError):pass
        pci.append(row)
        if category=='display':gpu_bus.append({'bus':'pci','id':row['slot'],'driver':row['driver'], 'vendor_id':vendor,'device_id':did})
        if category=='processing-accelerator-candidate': accelerator_candidates.append({'bus':'pci','id':row['slot'],'type':'processing-accelerator-candidate', 'confidence':'unverified'})
    usb=[]
    for item in _entries(bus/'usb/devices',256):
        vendor=_read(item/'idVendor',12); did=_read(item/'idProduct',12)
        if not vendor or not did:continue
        usb.append({'port':item.name[:40],'vendor_id':vendor,'product_id':did,
                    'manufacturer':_read(item/'manufacturer',80),'product':_read(item/'product',100),
                    'speed_mbps':_read(item/'speed',12)})
    gpu_render=[]
    for item in _entries(cls/'drm',64):
        if re.fullmatch(r'(card\d+|renderD\d+)',item.name):
            row={'node':item.name,'type':'render' if item.name.startswith('renderD') else 'display'}
            try:row['device_driver']=(item/'device/driver').resolve(strict=True).name[:60]
            except (OSError,RuntimeError):row['device_driver']=''
            gpu_render.append(row)
    accelerators=[]
    for item in _entries(cls/'accel',64):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',item.name):continue
        accelerators.append({'node':item.name,'type':'kernel-exposed-accelerator','status':'driver-exposed; compute readiness unverified'})
    categories={}
    for group,path,limit in [('block',cls/'block',64),('video',cls/'video4linux',32),
                             ('sound',cls/'sound',64),('bluetooth',cls/'bluetooth',32),
                             ('tty',cls/'tty',32),('hwmon',cls/'hwmon',32)]:
        entries=_entries(path,limit)
        # TTY and hwmon are broad; count and sample rather than claiming every physical device.
        categories[group]={'count_visible':len(entries),'truncated':len(entries)==limit,
                           'names':[p.name[:80] for p in entries]}
    cpu_model=''
    try:
        lines=(Path(procroot)/'cpuinfo').read_text(errors='replace')[:16384].splitlines()
        cpu_model=next((line.split(':',1)[1].strip()[:100] for line in lines if line.startswith(('model name','Hardware','Processor')) and ':' in line),'')
    except OSError:pass
    memory_mib=0
    try:
        match=re.search(r'^MemTotal:\s*(\d+) kB', (Path(procroot)/'meminfo').read_text(errors='replace'),re.M)
        if match:memory_mib=int(match.group(1))//1024
    except (OSError,ValueError):pass
    return {'networks':networks,'pci':pci,'usb':usb,'graphics':gpu_render,
            'gpu_bus':gpu_bus,'accelerators':accelerators,'accelerator_candidates':accelerator_candidates,
            'categories':categories,'cpu':{'model':cpu_model,'memory_mib':memory_mib,'logical_cores':os.cpu_count() or 1},
            'summary':{'network_interfaces':len(networks),'wireless_interfaces':len(wireless),
                       'pci_devices':len(pci),'usb_devices':len(usb),'render_devices':len(gpu_render),
                       'accelerators':len(accelerators),'accelerator_candidates':len(accelerator_candidates)},
            'warnings':['Read-only inventory shows devices visible to the FOXWORX Linux service; it cannot guarantee all physically attached hardware is exposed.',
                        'Monitor support is reported by iw when available; packet injection and NPU compute compatibility remain unverified.',
                        'Adapter role labels do not implement network namespaces, egress isolation or route changes.']}


class HardwareIntelligence:
    """Per-operator interface preferences over a short-lived host inventory."""
    def __init__(self,store,*,sysroot:Path=Path('/sys'),procroot:Path=Path('/proc')):
        self.store,self.sysroot,self.procroot=store,Path(sysroot),Path(procroot)
        self.cache:tuple[float,dict]|None=None

    def snapshot(self,*,fresh=False)->dict:
        if fresh or self.cache is None or time.monotonic()-self.cache[0]>15:
            self.cache=(time.monotonic(),discover(self.sysroot,self.procroot))
        return self.cache[1]

    @staticmethod
    def _key(owner,name):
        return hashlib.sha256((owner+'\0'+name).encode()).hexdigest()[:24]

    def inventory(self, owner:str, *,fresh=False)->dict:
        report=self.snapshot(fresh=fresh)
        decorated=[]
        for nic in report['networks']:
            saved=self.store.get('hardware-role',self._key(owner,nic['name']),owner)
            role=('management' if nic['protected'] else
                  saved.get('role','unassigned') if saved and saved.get('identity')==nic['identity'] else 'unassigned')
            decorated.append({**nic,'role':role,'role_source':'protected' if nic['protected'] else 'operator' if role!='unassigned' else 'discovered'})
        return {**report,'networks':decorated}

    def assign(self,owner:str,name:str,role:str)->dict:
        if not IFNAME.fullmatch(name):raise HTTPException(422,'Invalid interface name')
        if role not in ROLE_SET:raise HTTPException(422,'Role must be management, assessment or reserved')
        # Fresh inventory prevents writing obsolete roles after interface removal
        interfaces={n['name']:n for n in self.snapshot(fresh=True)['networks']}
        nic=interfaces.get(name)
        if not nic:raise HTTPException(404,'Interface is no longer present; refresh inventory')
        if nic['protected'] and role!='management':
            raise HTTPException(409,'Loopback/default-route interfaces are protected as management; changing the label cannot release them')
        key=self._key(owner,name)
        self.store.put('hardware-role',owner,{'id':key,'interface':name,'identity':nic['identity'],'role':role})
        self.store.event(owner,'hardware-role-updated',name+':'+role)
        return {'name':name,'role':role,'protected':nic['protected']}

    def require_assessment(self,owner:str,name:str)->dict:
        if not name or not IFNAME.fullmatch(name):raise HTTPException(422,'Choose a valid interface')
        for nic in self.inventory(owner,fresh=True)['networks']:
            if nic['name']==name:
                if nic['role']!='assessment' or nic['protected']:
                    raise HTTPException(403,'Select a nonmanagement interface assigned to assessment first')
                if nic['state']=='down':
                    raise HTTPException(409,'Selected assessment interface is down')
                return nic
        raise HTTPException(409,'Selected interface disappeared; refresh before submitting')
