import io
import json
import time
import zipfile
import pytest
from fastapi.testclient import TestClient
from foxworx.app import create_app

@pytest.fixture
def client(cfg):
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=("127.0.0.1",50000)) as c:
        yield c

@pytest.fixture
def logged(client,cfg):
    origin={'Origin':cfg.origin}
    assert client.post('/api/login',json={'token':cfg.local_token},headers=origin).status_code==200
    s=client.get('/api/session').json()
    client.headers.update({**origin,'X-Foxworx-CSRF':s['csrf']})
    return client

def test_unauthenticated_api_denied(client):
    assert client.get('/api/session').status_code==401

def test_bad_host_and_forwarded_local_rejected(client):
    assert client.get('/api/auth-mode',headers={'Host':'evil.test'}).status_code==403
    assert client.get('/api/auth-mode',headers={'CF-Connecting-IP':'192.0.2.1'}).status_code==403

def test_origin_and_csrf_required(logged):
    assert logged.post('/api/tools/refresh',json={},headers={'Origin':'https://evil.test'}).status_code==403
    assert logged.post('/api/tools/refresh',json={},headers={'X-Foxworx-CSRF':'wrong'}).status_code==403

def test_session_inventory_and_no_automatic_jobs(logged):
    data=logged.get('/api/session').json()
    assert data['version']=='3.3.3'
    assert len(logged.get('/api/tools').json()['tools'])>72
    assert logged.get('/api/jobs').json()==[]

def test_files_no_overwrite_or_traversal(logged):
    eng=logged.get('/api/engagements').json()[0]['id']
    route=f'/api/engagements/{eng}/files'
    assert logged.post(route,content=b'evidence',headers={'X-Filename':'hello.txt'}).status_code==200
    assert logged.post(route,content=b'overwrite',headers={'X-Filename':'hello.txt'}).status_code==409
    assert logged.post(route,content=b'escape',headers={'X-Filename':'../escape'}).status_code==400
    assert logged.get(route+'/hello.txt').content==b'evidence'
    root=logged.app.state.store.workspace(eng)
    (root/'link').symlink_to('/etc/passwd')
    assert logged.get(route+'/link').status_code==404
    bundle=logged.get(f'/api/engagements/{eng}/export?files=true')
    assert bundle.status_code==200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
        assert z.read('workspace/hello.txt')==b'evidence'
        assert 'workspace/link' not in z.namelist()
        assert 'manifest.json' in z.namelist()

def test_ai_unconfigured_clear_error(logged):
    eng=logged.get('/api/engagements').json()[0]['id']
    r=logged.post('/api/chat',json={'engagement_id':eng,'message':'explain nmap'})
    assert r.status_code==503 and 'not configured' in r.json()['detail']

def test_browser_socket_requires_ticket_and_reconnects(logged,cfg):
    eng=logged.get('/api/engagements').json()[0]['id']
    r=logged.post('/api/terminals',json={'engagement_id':eng})
    assert r.status_code==200
    tid=r.json()['id']
    ticket=logged.post(f'/api/terminals/{tid}/ticket',json={}).json()['ticket']
    with logged.websocket_connect(cfg.origin.replace('http://','ws://')+f'/ws/terminals/{tid}?ticket={ticket}',headers={'Origin':cfg.origin}) as ws:
        assert ws.receive_json()['type']=='ready'
        ws.send_json({'type':'input','data':"printf 'BROWSER-PTY-OK\\n'\n"})
        seen=''
        import base64
        for _ in range(30):
            msg=ws.receive_json()
            if msg['type']=='output': seen+=base64.b64decode(msg['data']).decode(errors='replace')
            if 'BROWSER-PTY-OK\r\n' in seen: break
        assert 'BROWSER-PTY-OK' in seen
    assert any(x['id']==tid for x in logged.get('/api/terminals').json())
    assert logged.request('DELETE',f'/api/terminals/{tid}',json={}).status_code==200

def test_job_history_is_filtered_before_recent_limit(logged):
    eng=logged.get('/api/engagements').json()[0]['id']
    store=logged.app.state.store
    old=store.put('job','local-operator',{'engagement_id':eng,'tool':'echo','status':'succeeded'})
    for _ in range(205):
        store.put('job','local-operator',{'engagement_id':'other-engagement','tool':'echo','status':'succeeded'})
    rows=logged.get('/api/jobs?engagement_id='+eng).json()
    assert any(j['id']==old['id'] for j in rows)


def test_diagnostics_exposes_gpu_summary_without_identifiers(logged,monkeypatch):
    import foxworx.app as api
    info={'architecture':'x86_64','profile':'workstation','device':'Linux host','supported':True,
          'distro':'kali','cpu_count':24,'gpu_count':3,'gpu_status':'available',
          'ollama_installed':True,'gpus':[{'index':i,'name':'RTX 3060 Ti','memory_mib':8192,'free_mib':7000,'driver_version':'580'} for i in range(3)], 'warnings':[]}
    monkeypatch.setattr(api,'host_snapshot',lambda **kwargs:info)
    result=logged.get('/api/diagnostics').json()
    assert result['hardware']['gpu_count']==3
    assert result['hardware']['profile']=='workstation'
    assert 'uuid' not in str(result)


def test_adapter_policy_read_only_authenticated_inventory(logged):
    res=logged.get('/api/adapter-policy')
    assert res.status_code==200
    body=res.json()
    assert len(body['profiles'])==17
    assert all(not x['enabled'] for x in body['profiles'])  # absent root policy
    assert body['status'] in ('missing','untrusted')
    assert logged.put('/api/adapter-policy',json={'enabled_profiles':['advanced']}).status_code==405


def test_unauthenticated_adapter_policy_denied(cfg):
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    with TestClient(create_app(cfg,_allow_root_for_tests=True),base_url=cfg.origin) as client:
        assert client.get('/api/adapter-policy').status_code in (401,403)

def test_graph_routes_authenticated_owner_scoped_and_annotated(logged):
    eng=logged.get('/api/engagements').json()[0]['id']
    store=logged.app.state.store
    job=store.put('job','local-operator',{'engagement_id':eng,'tool':'dig','status':'succeeded'})
    r=logged.get(f'/api/engagements/{eng}/graph');assert r.status_code==200
    assert any(n['id']=='job:'+job['id'] for n in r.json()['nodes'])
    note=logged.put(f'/api/engagements/{eng}/graph/notes',json={'node_id':'job:'+job['id'],'note':'Confirm observation in lab'})
    assert note.status_code==200
    assert any(n.get('note')=='Confirm observation in lab' for n in logged.get(f'/api/engagements/{eng}/graph').json()['nodes'])
    assert logged.get(f'/api/engagements/{"f"*24}/graph').status_code==404
    assert logged.put(f'/api/engagements/{eng}/graph/notes',json={'node_id':'job:'+'f'*24,'note':'fake'}).status_code==404
    assert logged.put(f'/api/engagements/{eng}/graph/notes',json={'node_id':'job:'+job['id'],'note':'x'*1201}).status_code==422
    assert logged.put(f'/api/engagements/{eng}/graph/notes',json={'node_id':'job:'+job['id'],'note':'', 'unexpected':'x'}).status_code==422
