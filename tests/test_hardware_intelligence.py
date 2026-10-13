"""Hardware Intelligence: Linux-visible inventory, role boundaries and job binding."""
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from fastapi import HTTPException
from foxworx.hardware_intelligence import discover,HardwareIntelligence
from foxworx.jobs import JobManager
from foxworx.registry import Registry
from foxworx.models import ProposalSpec


def create_fake_linux(tmp_path):
    sysroot=tmp_path/'sys'; proc=tmp_path/'proc'
    def write(path,value):
        f=sysroot/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(str(value))
    for name in ('lo','eth0','wlan1'):
        write(Path('class/net')/name/'operstate','up')
        write(Path('class/net')/name/'mtu','1500')
        write(Path('class/net')/name/'ifindex',{'lo':1,'eth0':2,'wlan1':3}[name])
        write(Path('class/net')/name/'address',{'lo':'00:00:00:00:00:00','eth0':'12:34:56:78:90:ab','wlan1':'a1:b2:c3:d4:e5:f6'}[name])
    (sysroot/'class/net/wlan1/wireless').mkdir()
    (sysroot/'class/net/wlan1/phy80211').symlink_to('phy0')
    write(Path('bus/pci/devices/0000:02:00.0/class'),'0x030000')
    write(Path('bus/pci/devices/0000:02:00.0/vendor'),'0x10de')
    write(Path('bus/pci/devices/0000:02:00.0/device'),'0x2489')
    write(Path('bus/pci/devices/0000:02:00.0/numa_node'),'0')
    write(Path('bus/pci/devices/0000:04:00.0/class'),'0x120000')
    write(Path('bus/pci/devices/0000:04:00.0/vendor'),'0x8086')
    write(Path('bus/pci/devices/0000:04:00.0/device'),'0x0001')
    write(Path('bus/usb/devices/2-1/idVendor'),'0bda')
    write(Path('bus/usb/devices/2-1/idProduct'),'8812')
    write(Path('bus/usb/devices/2-1/product'),'Wireless Adapter')
    write(Path('bus/usb/devices/2-1/manufacturer'),'Lab test vendor')
    write(Path('bus/usb/devices/2-1/serial'),'SECRET-DO-NOT-EXPOSE')
    write(Path('class/drm/renderD128/uevent'),'MAJOR=226')
    write(Path('class/accel/accel0/uevent'),'MAJOR=261')
    write(Path('class/block/sda/size'),'80000')
    write(Path('class/video4linux/video0/uevent'),'MAJOR=81')
    (proc/'net').mkdir(parents=True)
    (proc/'net/route').write_text('Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\neth0 00000000 00000000 0003 0 0 0 00000000 0 0 0\nwlan1 00010203 00000000 0001 0 0 0 000000FF 0 0 0\n')
    (proc/'cpuinfo').write_text('model name\t: FOXWORX Test CPU\nSerial: SHOULD-NOT-APPEAR\n')
    (proc/'meminfo').write_text('MemTotal:       8192000 kB\n')
    return sysroot,proc


def test_full_inventory_and_sanitized_sensitive_identifiers(tmp_path,monkeypatch):
    sysroot,proc=create_fake_linux(tmp_path)
    monkeypatch.setattr('foxworx.hardware_intelligence._monitor_support',lambda phy,iw:'supported' if phy=='phy0' else 'unknown')
    snap=discover(sysroot,proc,iw='/usr/bin/iw')
    assert snap['summary']=={'network_interfaces':3,'wireless_interfaces':1,'pci_devices':2,'usb_devices':1,
                             'render_devices':1,'accelerators':1,'accelerator_candidates':1}
    assert snap['cpu']['memory_mib']==8000
    eth=next(n for n in snap['networks'] if n['name']=='eth0')
    wifi=next(n for n in snap['networks'] if n['name']=='wlan1')
    assert eth['protected'] and eth['default_route']
    assert wifi['monitor_mode']=='supported' and wifi['packet_injection']=='unverified'
    assert not wifi['protected']
    assert snap['accelerator_candidates'][0]['confidence']=='unverified'
    serialized=json.dumps(snap)
    assert 'SECRET-DO-NOT-EXPOSE' not in serialized
    assert 'a1:b2:c3:d4:e5:f6' not in serialized
    assert 'SHOULD-NOT-APPEAR' not in serialized


def test_wireless_mode_query_is_read_only_and_bounded(monkeypatch):
    from foxworx.hardware_intelligence import _monitor_support
    calls=[]
    def run(argv,**kw):
        calls.append((argv,kw))
        return SimpleNamespace(returncode=0,stdout='Wiphy phy0\n\tSupported interface modes:\n\t\t * managed\n\t\t * monitor\n')
    monkeypatch.setattr('foxworx.hardware_intelligence.subprocess.run',run)
    assert _monitor_support('phy0','/usr/bin/iw')=='supported'
    assert calls[0][0]==['/usr/bin/iw','phy','phy0','info']
    assert calls[0][1]['timeout']<=3
    assert _monitor_support('evil;cmd','/usr/bin/iw')=='unknown'
    assert len(calls)==1


def test_role_persistence_protected_route_and_hardware_change(tmp_path,store):
    sysroot,proc=create_fake_linux(tmp_path)
    engine=HardwareIntelligence(store,sysroot=sysroot,procroot=proc)
    owner='operator-a'
    result=engine.inventory(owner)
    assert next(n for n in result['networks'] if n['name']=='eth0')['role']=='management'
    with pytest.raises(HTTPException) as bad:
        engine.assign(owner,'eth0','assessment')
    assert bad.value.status_code==409
    with pytest.raises(HTTPException):engine.assign(owner,'lo','assessment')
    with pytest.raises(HTTPException):engine.assign(owner,'wlan1','not-a-real-role')
    assert engine.assign(owner,'wlan1','assessment')['role']=='assessment'
    assert engine.require_assessment(owner,'wlan1')['name']=='wlan1'
    assert next(n for n in engine.inventory('operator-b')['networks'] if n['name']=='wlan1')['role']=='unassigned'
    # Fresh engine reproduces saved role from SQLite.
    engine2=HardwareIntelligence(store,sysroot=sysroot,procroot=proc)
    assert next(n for n in engine2.inventory(owner)['networks'] if n['name']=='wlan1')['role']=='assessment'
    (sysroot/'class/net/wlan1/address').write_text('different-mac')
    with pytest.raises(HTTPException):engine2.require_assessment(owner,'wlan1')
    assert next(n for n in engine2.inventory(owner, fresh=True)['networks'] if n['name']=='wlan1')['role']=='unassigned'


def test_role_protects_after_route_change(tmp_path,store):
    sysroot,proc=create_fake_linux(tmp_path)
    engine=HardwareIntelligence(store,sysroot=sysroot,procroot=proc)
    engine.assign('alice','wlan1','assessment')
    with (proc/'net/route').open('a') as f:
        f.write('wlan1 00000000 00000000 0003 0 0 0 00000000 0 0 0\n')
    with pytest.raises(HTTPException) as exc:
        engine.require_assessment('alice','wlan1')
    assert exc.value.status_code==403
    assert next(n for n in engine.inventory('alice')['networks'] if n['name']=='wlan1')['protected']


def test_managed_curl_bind_requires_review_and_checks_role_at_approval(tmp_path,store,cfg,monkeypatch):
    sysroot,proc=create_fake_linux(tmp_path)
    engine=HardwareIntelligence(store,sysroot=sysroot,procroot=proc)
    engine.assign('alice','wlan1','assessment')
    registry=Registry(cfg)
    manager=JobManager(cfg,store,registry)
    manager.hardware=engine
    # Use the system curl only if it is installed, with a normal registry scan.
    registry.scan()
    if not any(x['name']=='curl' and x['installed'] for x in registry.list()):pytest.skip('curl not on build host')
    eng=store.put('engagement','alice',{'name':'lab','include':['http://127.0.0.1'],'exclude':[],'notes':''})
    spec=ProposalSpec(engagement_id=eng['id'],tool='curl',profile='http-headers',target='http://127.0.0.1',interface_name='wlan1')
    proposal=manager.prepare('alice',spec)
    assert proposal['argv'][1:3]==['--interface','if!wlan1']
    assert proposal['interface_identity']
    with pytest.raises(HTTPException):
        manager.prepare('alice',spec.model_copy(update={'interface_name':'eth0'}))
    with pytest.raises(HTTPException):
        manager.prepare('alice',spec.model_copy(update={'profile':'advanced','args':['--help']}))
    # Link becomes default route after proposal but before approval: cannot proceed.
    with (proc/'net/route').open('a') as f:
        f.write('wlan1 00000000 00000000 0003 0 0 0 00000000 0 0 0\n')
    import asyncio
    with pytest.raises(HTTPException) as exc:
        asyncio.run(manager.approve('alice',proposal['id'],proposal['digest'],True))
    assert exc.value.status_code==403


@pytest.fixture
def logged(cfg):
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    with TestClient(create_app(cfg,_allow_root_for_tests=True),base_url=cfg.origin,client=('127.0.0.1',50000)) as client:
        headers={'Origin':cfg.origin}
        assert client.post('/api/login',json={'token':cfg.local_token},headers=headers).status_code==200
        session=client.get('/api/session').json()
        client.headers.update({**headers,'X-Foxworx-CSRF':session['csrf']})
        yield client


def test_hardware_api_owner_validation_and_read_only(logged,tmp_path):
    sysroot,proc=create_fake_linux(tmp_path)
    engine=logged.app.state.hardware
    engine.sysroot=sysroot;engine.procroot=proc;engine.cache=None
    r=logged.get('/api/hardware?fresh=true');assert r.status_code==200
    assert len(r.json()['networks'])==3
    assert logged.put('/api/hardware/interfaces/eth0/role',json={'role':'assessment'}).status_code==409
    assert logged.put('/api/hardware/interfaces/wlan1/role',json={'role':'assessment'}).status_code==200
    assert next(x for x in logged.get('/api/hardware').json()['networks'] if x['name']=='wlan1')['role']=='assessment'
    assert logged.put('/api/hardware/interfaces/wlan1/role',json={'role':'assessment','command':'ip link set down'}).status_code==422
    assert logged.put('/api/hardware/interfaces/wlan1/role',json={'role':'root'}).status_code==422
    assert logged.post('/api/hardware').status_code==405


def test_hardware_api_requires_login_and_role_changes_require_csrf(cfg,tmp_path):
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    with TestClient(create_app(cfg,_allow_root_for_tests=True),base_url=cfg.origin,client=('127.0.0.1',50000)) as client:
        assert client.get('/api/hardware').status_code==401
        assert client.put('/api/hardware/interfaces/wlan1/role',json={'role':'assessment'}).status_code in (401,403)
        assert client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        sysroot,proc=create_fake_linux(tmp_path)
        engine=client.app.state.hardware
        engine.sysroot=sysroot;engine.procroot=proc;engine.cache=None
        assert client.get('/api/hardware').status_code==200
        assert client.put('/api/hardware/interfaces/wlan1/role',json={'role':'assessment'},headers={'Origin':cfg.origin}).status_code==403
        csrf=client.get('/api/session').json()['csrf']
        assert client.put('/api/hardware/interfaces/wlan1/role',json={'role':'assessment'},headers={'Origin':cfg.origin,'X-Foxworx-CSRF':csrf}).status_code==200
