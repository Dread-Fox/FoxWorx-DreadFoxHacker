"""Native Codex integration tests. Fake app-server: NEVER sign in to a real account in CI."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from foxworx.codex_agent import CodexAgent, CodexProcess, safe_account
from foxworx.app import create_app
from fastapi.testclient import TestClient
from foxworx.jobs import JobManager
from foxworx.registry import Registry


class FakeCodex:
    instances=[]
    authenticated=False
    auth_url='https://auth.openai.com/codex/device'
    def __init__(self, executable, env, on_notification=None):
        self.executable=executable; self.env=env; self.on_notification=on_notification
        self.proc=SimpleNamespace(returncode=None); self.commands=[]; self.connected=False
        self.__class__.instances.append(self)
    async def start(self): return self
    async def stop(self):self.proc.returncode=0
    async def call(self, method, params=None, timeout=20):
        self.commands.append((method,params))
        if method=='account/read':
            return {'account':{'type':'chatgpt','planType':'plus','email':'operator@example.test'} if self.connected else None}
        if method=='account/login/start':
            assert params=={'type':'chatgptDeviceCode'}
            return {'verificationUrl':self.auth_url,'userCode':'ABCD-1234','loginId':'internal-only'}
        if method=='account/logout':self.connected=False;return {}
        if method=='thread/start':return {'thread':{'id':'codex-fixture-thread'}}
        if method=='thread/resume':return {'thread':{'id':params['threadId']}}
        if method=='turn/start':
            self.on_notification({'method':'item/agentMessage/delta','params':{'delta':json.dumps({'content':'Laboratory analysis completed.','calls':[]})}})
            self.on_notification({'method':'turn/completed','params':{'turn':{'status':'completed'}}})
            return {'turn':{'id':'fixture-turn','status':'inProgress','items':[],'error':None}}
        return {}

@pytest.fixture
def codex(cfg,store,monkeypatch):
    FakeCodex.instances=[]
    jobs=JobManager(cfg,store,Registry(cfg))
    c=CodexAgent(cfg,store,jobs,proc_factory=FakeCodex)
    monkeypatch.setattr(c,'installed',lambda:'/opt/codex/bin/codex')
    return c

@pytest.mark.asyncio
async def test_device_login_account_owner_separation_and_no_credentials_in_browser(codex,cfg):
    login=await codex.login('alice@example.test')
    assert login=={'verification_url':FakeCodex.auth_url,'user_code':'ABCD-1234','status':'pending'}
    alice=await codex.status('alice@example.test')
    assert alice['login']=={'pending':True,'success':False,'error':''}
    assert 'ABCD-1234' not in str(alice) and 'internal-only' not in str(alice)
    bob=await codex.status('bob@example.test')
    assert bob['login']=={} and not bob['connected']
    assert len(FakeCodex.instances)==2
    a,b=FakeCodex.instances
    assert a.env['CODEX_HOME']!=b.env['CODEX_HOME']
    assert Path(a.env['CODEX_HOME']).stat().st_mode & 0o077==0
    assert 'OPENAI_API_KEY' not in a.env and 'CODEX_API_KEY' not in a.env
    assert a.commands[0]==('account/login/start',{'type':'chatgptDeviceCode'})
    await codex.shutdown()

@pytest.mark.asyncio
async def test_invalid_device_url_rejected(codex,monkeypatch):
    monkeypatch.setattr(FakeCodex,'auth_url','https://attacker.example/enter-password')
    with pytest.raises(HTTPException) as err:await codex.login('alice')
    assert err.value.status_code==502
    await codex.shutdown()
    monkeypatch.setattr(FakeCodex,'auth_url','https://auth.openai.com/codex/device')

@pytest.mark.asyncio
async def test_agent_needs_login_even_when_executable_installed(codex,engagement):
    with pytest.raises(HTTPException) as err:
        await codex.complete('local-operator','default',[{'role':'user','content':'Explain headers'}],[])
    assert err.value.status_code==409
    assert codex.running=={}
    await codex.shutdown()

@pytest.mark.asyncio
async def test_native_codex_inference_is_ephemeral_and_legacy_history_is_preserved(codex,engagement,store):
    p=await codex._server('local-operator')
    p.connected=True
    answer=await codex.complete('local-operator','default',[{'role':'user','content':'Explain the service check'}],[])
    assert answer['content']=='Laboratory analysis completed.'
    begin=next(params for method,params in p.commands if method=='thread/start')
    assert begin['sandbox']=='read-only' and begin['approvalPolicy']=='never'
    assert begin['ephemeral'] is True
    assert begin['cwd'].startswith(str(codex.cfg.state/'codex-workspaces'))
    assert all(a!='apiKey' for a in p.commands)
    store.put('codex-turn','local-operator',{'engagement_id':engagement['id'],'prompt':'Archived legacy question','answer':'Archived legacy answer'})
    history=await codex.history('local-operator',engagement['id'])
    assert len(history)==1 and history[0]['prompt']=='Archived legacy question'
    assert 'token' not in str(history).lower() and codex.running=={}
    answer2=await codex.complete('local-operator','default',[{'role':'user','content':'Second step'}],[])
    assert answer2['content']=='Laboratory analysis completed.'
    assert not any(method=='thread/resume' for method,_ in p.commands)
    await codex.shutdown()

@pytest.mark.asyncio
async def test_unauthorized_engagement_denied(codex):
    with pytest.raises(HTTPException) as err:
        await codex.history('alice','nonexistent')
    assert err.value.status_code==404

@pytest.mark.asyncio
async def test_completed_device_auth_status_safe(codex):
    await codex.login('alice')
    proc=codex.processes['alice']
    proc.connected=True
    proc.on_notification({'method':'account/login/completed','params':{'success':True,'loginId':'internal-only'}})
    s=await codex.status('alice')
    assert s['connected'] and s['login']['success']
    assert 'ABCD-1234' not in str(s) and 'internal-only' not in str(s)
    await codex.logout('alice')
    assert not (await codex.status('alice'))['connected']
    await codex.shutdown()

@pytest.mark.asyncio
async def test_missing_codex_binary_returns_safe_status(cfg,store):
    jobs=JobManager(cfg,store,Registry(cfg)); c=CodexAgent(cfg,store,jobs)
    c.installed=lambda:None
    data=await c.status('alice')
    assert data['installed'] is False and data['connected'] is False
    with pytest.raises(HTTPException) as err:await c.login('alice')
    assert err.value.status_code==503


def test_http_routes_require_auth_and_csrf(cfg,monkeypatch):
    monkeypatch.setattr(CodexAgent,'installed',lambda self:None)
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50445)) as c:
        assert c.get('/api/codex/status').status_code==401
        assert c.post('/api/codex/login',json={}).status_code in (401,403)
        assert c.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        assert c.get('/api/codex/status').json()['installed'] is False
        assert c.post('/api/codex/login',json={},headers={'Origin':cfg.origin}).status_code==403
        csrf=c.get('/api/session').json()['csrf']
        assert c.post('/api/codex/login',json={},headers={'Origin':cfg.origin,'X-Foxworx-CSRF':csrf}).status_code==503

@pytest.mark.asyncio
async def test_codex_app_server_real_stdio_transport_denies_server_approval(tmp_path):
    """Prove the JSON-RPC wire handshake works against a local fake child process."""
    import sys
    path=tmp_path/'fake-codex'
    path.write_text('#!'+sys.executable+'\n'+'''import json,sys
for line in sys.stdin:
    msg=json.loads(line)
    if msg.get('method')=='initialize':
        print(json.dumps({'id':msg['id'],'result':{'userAgent':'fake'}}),flush=True)
    elif msg.get('method')=='account/read':
        print(json.dumps({'id':msg['id'],'result':{'account':None}}),flush=True)
        print(json.dumps({'id':901,'method':'item/commandExecution/requestApproval','params':{'dangerous':True}}),flush=True)
    elif msg.get('id')==901:
        # The permission response must never approve the child request.
        assert msg.get('result',{}).get('decision')=='decline'
''')
    path.chmod(0o700)
    notifications=[]
    p=CodexProcess(str(path),{'PATH':'/usr/bin:/bin'},notifications.append)
    try:
        await p.start()
        assert await p.call('account/read',{'refreshToken':False})=={'account':None}
        for _ in range(30):
            if any(e.get('method')=='foxworx/approval/denied' for e in notifications):break
            await asyncio.sleep(.02)
        assert any(e.get('method')=='foxworx/approval/denied' for e in notifications)
    finally:await p.stop()

@pytest.mark.asyncio
async def test_operator_can_request_codex_interruption(codex):
    with pytest.raises(HTTPException) as err:await codex.interrupt('alice')
    assert err.value.status_code==409
    p=await codex._server('alice')
    codex.running['alice']='authorized-engagement';codex.active_threads['alice']='running-thread'
    codex.active_turns['alice']='running-turn'
    assert (await codex.interrupt('alice'))['stop_requested'] is True
    assert ('turn/interrupt',{'threadId':'running-thread','turnId':'running-turn'}) in p.commands
    await codex.shutdown()
