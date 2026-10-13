"""Rabbit Hole must not silently turn the Kali shell into an unconstrained agent."""
import asyncio
import json
import time
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from foxworx.models import RabbitSpec
from foxworx.rabbit import RabbitRunner

@pytest.fixture(autouse=True)
def trusted_test_policy(monkeypatch):
    """Rabbit unit/API tests intentionally inject a trusted test policy.

    Production always reads the root-owned file. Dedicated adapter tests prove
    untrusted/missing policies fail closed.
    """
    from foxworx.adapters import AdapterPolicy, ADAPTERS
    monkeypatch.setattr(AdapterPolicy,'current',lambda self: {
        'status':'active','revision':'test-policy-v1',
        'enabled_profiles':tuple(ADAPTERS),'max_steps':16,'max_minutes':30})

OWNER='local-operator'

def grant(engagement, **overrides):
    values={'engagement_id':engagement['id'], 'objective':'Identify the local lab HTTP service',
            'target':'127.0.0.1', 'profiles':['http-headers','tcp-connect'],
            'max_steps':4, 'max_minutes':2, 'authorized':True}
    values.update(overrides)
    return RabbitSpec(**values)

class StubJobs:
    def __init__(self, engagement):
        self.eng = engagement
        self.commands=[]
        self.statuses=[]
        self.stopped=[]
        self.registry = None
        self.directory = None
    def engagement(self, owner, id):
        assert owner == OWNER
        if id != self.eng['id']: raise HTTPException(404,'Engagement not found')
        return self.eng
    def prepare(self, owner, spec, source='operator'):
        assert source == 'rabbit-hole'
        assert spec.profile != 'advanced'
        assert spec.target in ('127.0.0.1','http://127.0.0.1/')
        self.commands.append(spec.profile)
        return {'id':'proposal-'+str(len(self.commands)), 'digest':'a'*64}
    async def approve(self, owner, id, digest, authorized):
        assert authorized and digest=='a'*64
        return {'id':'job-'+str(len(self.commands)), 'status':'queued'}
    def delegate(self,owner,proposal,run_id,instruction_revision):
        return proposal
    async def stop(self, owner, id):
        self.stopped.append(id)
    def output(self, id, owner, offset=0):
        return {'text':'Connection failed: refused on local lab', 'job':{'status':'failed'}}

def tool_choice(profile):
    return {'content':'', 'calls':[{'id':'c1','name':'choose_workflow','arguments':json.dumps({'profile':profile,'reason':'Try a permitted diagnostic'})}]}

def finish(status='solved', summary='Found a result', next_steps='No more steps'):
    return {'content':'','calls':[{'id':'c1','name':'finish_run','arguments':json.dumps({'status':status,'summary':summary,'next_steps':next_steps})}]}

class FakeGateway:
    def __init__(self, replies): self.replies=list(replies); self.requests=[]
    async def complete(self, route, messages, tools):
        self.requests.append((route,messages,tools))
        return self.replies.pop(0) if self.replies else finish('blocked','No more options','Inspect manually')

class FakeProviders:
    def resolve(self, owner):
        return {'provider':'ollama','model_id':'stub','model':'ollama_chat/stub','api_base':'http://127.0.0.1:11434'}

async def settle(store, runner, rid):
    for _ in range(150):
        r=store.get('rabbit',rid,OWNER)
        if r['status'] not in ('queued','running','stopping'): return r
        await asyncio.sleep(.01)
    raise AssertionError('Rabbit task did not finish')

@pytest.fixture
def setup(cfg, store, engagement):
    jobs=StubJobs(engagement)
    gateway=FakeGateway([finish()])
    runner=RabbitRunner(cfg,store,jobs,FakeProviders(),gateway)
    return runner,jobs,gateway

@pytest.mark.asyncio
async def test_run_requires_explicit_one_time_authorization(setup, engagement):
    runner,jobs,_=setup
    with pytest.raises(HTTPException) as error:
        runner.start(OWNER,grant(engagement,authorized=False))
    assert error.value.status_code==403
    assert not jobs.commands

@pytest.mark.asyncio
async def test_scope_must_contain_exact_target(setup, engagement):
    runner,jobs,_=setup
    with pytest.raises(HTTPException) as error:
        runner.start(OWNER,grant(engagement,target='192.0.2.1'))
    assert error.value.status_code==403
    assert not jobs.commands

@pytest.mark.parametrize('values',[
    {'profiles':['advanced']}, {'profiles':[]}, {'max_steps':10001}, {'max_minutes':0},
    {'target':'http://127.0.0.1/\nother'},
])
def test_invalid_grants_rejected(engagement,values):
    with pytest.raises(ValidationError): grant(engagement,**values)

@pytest.mark.asyncio
async def test_agent_can_retry_failed_job_and_finish(setup, engagement, monkeypatch):
    runner,jobs,gateway=setup
    gateway.replies=[tool_choice('http-headers'),tool_choice('tcp-connect'),finish('solved','The scan identified a service','Review evidence')]
    jobs.statuses=['failed','succeeded']
    async def pretend_wait(owner,jid,deadline,run_id):
        await asyncio.sleep(0)
        return {'id':jid,'status':jobs.statuses.pop(0),'returncode':0}
    monkeypatch.setattr(runner,'_wait_job',pretend_wait)
    record=runner.start(OWNER,grant(engagement))
    ended=await settle(runner.store,runner,record['id'])
    assert ended['status']=='solved'
    assert jobs.commands==['http-headers','tcp-connect']
    assert len(ended['steps'])==2
    assert ended['steps'][0]['status']=='failed'
    assert ended['steps'][1]['status']=='succeeded'
    assert len(gateway.requests)==3
    assert any('Connection failed' in str(call[1]) for call in gateway.requests[1:])

@pytest.mark.asyncio
async def test_cannot_execute_profile_not_in_grant(setup, engagement):
    runner,jobs,gateway=setup
    gateway.replies=[tool_choice('whois'),tool_choice('whois'),finish('blocked')]
    ended=await settle(runner.store,runner,runner.start(OWNER,grant(engagement))['id'])
    assert not jobs.commands
    assert ended['status']=='blocked'
    assert 'authorized' in ended['summary'].lower()

@pytest.mark.asyncio
async def test_repeat_loop_and_iteration_ceiling(setup, engagement, monkeypatch):
    runner,jobs,gateway=setup
    gateway.replies=[tool_choice('http-headers')]*10
    async def pretend_wait(owner,jid,deadline,run_id): return {'id':jid,'status':'failed','returncode':1}
    monkeypatch.setattr(runner,'_wait_job',pretend_wait)
    ended=await settle(runner.store,runner,runner.start(OWNER,grant(engagement,max_steps=3))['id'])
    assert ended['status']=='blocked'
    assert 1<=len(jobs.commands)<=3
    assert len(ended['steps'])<=3

@pytest.mark.asyncio
async def test_scope_change_before_next_iteration_blocks(setup, engagement, monkeypatch):
    runner,jobs,gateway=setup
    gateway.replies=[tool_choice('http-headers'),tool_choice('tcp-connect')]
    async def pretend_wait(owner,jid,deadline,run_id):
        jobs.eng={**jobs.eng,'notes':'Automation is now prohibited'}
        return {'id':jid,'status':'succeeded','returncode':0}
    monkeypatch.setattr(runner,'_wait_job',pretend_wait)
    ended=await settle(runner.store,runner,runner.start(OWNER,grant(engagement))['id'])
    assert ended['status']=='blocked'
    assert jobs.commands==['http-headers']
    assert 'scope' in ended['summary'].lower() or 'authorization' in ended['summary'].lower()

@pytest.mark.asyncio
async def test_stop_prevents_more_commands(setup, engagement, monkeypatch):
    runner,jobs,gateway=setup
    gateway.replies=[tool_choice('http-headers')]*4
    started=asyncio.Event()
    async def pretend_wait(owner,jid,deadline,run_id):
        started.set()
        await asyncio.sleep(3600)
    monkeypatch.setattr(runner,'_wait_job',pretend_wait)
    rid=runner.start(OWNER,grant(engagement))['id']
    await asyncio.wait_for(started.wait(),1)
    await runner.stop(OWNER,rid)
    ended=await settle(runner.store,runner,rid)
    assert ended['status']=='stopped'
    assert len(jobs.commands)==1
    assert jobs.stopped

@pytest.mark.asyncio
async def test_owner_cannot_read_or_stop_another_users_run(setup, engagement):
    runner,_,_=setup
    rid=runner.start(OWNER,grant(engagement))['id']
    with pytest.raises(HTTPException) as err: runner.get('elsewhere',rid)
    assert err.value.status_code==404
    with pytest.raises(HTTPException): await runner.stop('elsewhere',rid)
    await settle(runner.store,runner,rid)

@pytest.mark.asyncio
async def test_restart_marks_in_progress_as_interrupted(setup, engagement):
    runner,_,_=setup
    stored=runner.store.put('rabbit', OWNER,{'engagement_id':engagement['id'],'status':'running'})
    runner.recover()
    assert runner.store.get('rabbit',stored['id'],OWNER)['status']=='interrupted'

@pytest.mark.asyncio
async def test_only_one_active_run_per_owner(setup,engagement,monkeypatch):
    runner,jobs,gateway=setup
    event=asyncio.Event()
    async def slow(route,messages,tools):
        event.set();await asyncio.sleep(3600)
    monkeypatch.setattr(gateway,'complete',slow)
    r=runner.start(OWNER,grant(engagement))
    await event.wait()
    with pytest.raises(HTTPException) as e: runner.start(OWNER,grant(engagement))
    assert e.value.status_code==429
    await runner.stop(OWNER,r['id'])



def test_api_requires_login_and_valid_approval(cfg):
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',49999)) as client:
        assert client.get('/api/rabbit-runs').status_code==401
        assert client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        csrf=client.get('/api/session').json()['csrf']
        client.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':csrf})
        eng=client.get('/api/engagements').json()[0]
        selection=client.put('/api/ai/settings',json={'provider':'ollama','model':'qwen3:8b','endpoint_id':'ollama-local'})
        assert selection.status_code==200
        req=grant(eng,profiles=['tcp-connect']).model_dump()
        req['authorized']=False
        assert client.post('/api/rabbit-runs',json=req).status_code==403
        assert client.get('/api/rabbit-runs').json()==[]


def test_api_run_and_status_without_repeated_operator_confirmation(cfg):
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',49999)) as client:
        client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin})
        csrf=client.get('/api/session').json()['csrf']
        client.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':csrf})
        eng=client.get('/api/engagements').json()[0]
        client.put('/api/ai/settings',json={'provider':'ollama','model':'qwen3:8b','endpoint_id':'ollama-local'})
        async def reply(route,messages,tools): return finish('blocked','No verified workflow available','Check the environment')
        app.state.rabbit.gateway.complete=reply
        start=client.post('/api/rabbit-runs',json=grant(eng,profiles=['tcp-connect']).model_dump())
        assert start.status_code==200,start.text
        rid=start.json()['id']
        assert any(x['id']==rid for x in client.get('/api/rabbit-runs').json())
        import time
        for _ in range(100):
            detail=client.get('/api/rabbit-runs/'+rid)
            assert detail.status_code==200
            if detail.json()['status'] not in ('running','queued'): break
            time.sleep(.01)
        assert detail.json()['status']=='blocked'
        assert client.post('/api/rabbit-runs/'+rid+'/stop',json={}).status_code==200

def test_real_managed_curl_job_runs_under_single_rabbit_authorization(cfg):
    """Local-only smoke: test actual subprocess creation, capture and autonomous finish."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    from foxworx.registry import Registry
    from shutil import which
    if not which('curl'): pytest.skip('curl is unavailable in the build environment')
    class Lab(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(200)
            self.send_header('X-Foxworx-Lab','true')
            self.end_headers()
        def log_message(self,*args): pass
    lab=ThreadingHTTPServer(('127.0.0.1',0),Lab)
    thread=threading.Thread(target=lab.serve_forever,daemon=True);thread.start()
    try:
        app=create_app(cfg,_allow_root_for_tests=True)
        with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',49999)) as client:
            client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin})
            csrf=client.get('/api/session').json()['csrf']
            client.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':csrf})
            engagement=client.get('/api/engagements').json()[0]
            client.put('/api/ai/settings',json={'provider':'ollama','model':'qwen3:8b','endpoint_id':'ollama-local'})
            response_list=[tool_choice('http-headers'),finish('solved','Local HTTP server responded','Review HTTP headers')]
            async def fake(route,messages,tools): return response_list.pop(0)
            app.state.rabbit.gateway.complete=fake
            target=f'http://127.0.0.1:{lab.server_port}/'
            payload=grant(engagement,profiles=['http-headers'],target=target).model_dump()
            started=client.post('/api/rabbit-runs',json=payload)
            assert started.status_code==200,started.text
            run_id=started.json()['id']
            import time
            for _ in range(200):
                run=client.get('/api/rabbit-runs/'+run_id).json()
                if run['status'] not in ('queued','running','stopping'):break
                time.sleep(.05)
            assert run['status']=='solved',run
            assert len(run['steps'])==1
            assert run['steps'][0]['status']=='succeeded'
            job=client.get('/api/jobs/'+run['steps'][0]['job_id']+'/output')
            assert job.status_code==200 and '200 OK' in job.json()['text']
            assert 'X-Foxworx-Lab' in job.json()['text']
            assert any(event['action']=='rabbit-auto-job' for event in app.state.store.events(OWNER))
    finally:
        lab.shutdown();lab.server_close();thread.join(timeout=2)

@pytest.mark.asyncio
async def test_policy_revoked_after_a_tool_result_blocks_next_attempt(setup,engagement,monkeypatch):
    runner,jobs,gateway=setup
    gateway.replies=[tool_choice('http-headers'),tool_choice('tcp-connect')]
    policy={'status':'active','revision':'test-policy-v1','enabled_profiles':('http-headers','tcp-connect'),
            'max_steps':16,'max_minutes':30}
    monkeypatch.setattr(runner.policy,'current',lambda:dict(policy))
    async def after_first(owner,jid,deadline,run_id):
        policy['revision']='root-revoked-policy-v2'
        return {'id':jid,'status':'succeeded','returncode':0}
    monkeypatch.setattr(runner,'_wait_job',after_first)
    ended=await settle(runner.store,runner,runner.start(OWNER,grant(engagement))['id'])
    assert ended['status']=='blocked'
    assert jobs.commands==['http-headers']
    assert 'policy' in ended['summary'].lower()

@pytest.mark.asyncio
async def test_policy_change_cancels_active_job(setup,engagement,monkeypatch):
    runner,jobs,_=setup
    policy={'status':'active','revision':'test-policy-v1','enabled_profiles':('http-headers',),
            'max_steps':16,'max_minutes':30}
    monkeypatch.setattr(runner.policy,'current',lambda:dict(policy))
    run=runner.start(OWNER,grant(engagement,profiles=['http-headers']))
    runner.tasks[run['id']].cancel()
    await asyncio.gather(*list(runner.tasks.values()),return_exceptions=True)
    job=runner.store.put('job',OWNER,{'id':'job-pending-test','status':'running'})
    policy['revision']='admin-replaced-policy'
    with pytest.raises(RuntimeError,match='policy'):
        await runner._wait_job(OWNER,job['id'],time.time()+30,run['id'])
    assert job['id'] in jobs.stopped


def test_missing_admin_policy_blocks_even_operator_approved_run(setup,engagement,monkeypatch):
    runner,jobs,_=setup
    monkeypatch.setattr(runner.policy,'current',lambda:{'status':'missing','revision':'disabled',
        'enabled_profiles':(), 'max_steps':0, 'max_minutes':0})
    with pytest.raises(HTTPException) as error:
        runner.start(OWNER,grant(engagement))
    assert error.value.status_code==503
    assert not jobs.commands


def test_admin_maximum_budget_overrides_operator_request(setup,engagement,monkeypatch):
    runner,jobs,_=setup
    monkeypatch.setattr(runner.policy,'current',lambda:{'status':'active','revision':'budget-v1',
        'enabled_profiles':('http-headers','tcp-connect'), 'max_steps':3, 'max_minutes':1})
    with pytest.raises(HTTPException) as error:
        runner.start(OWNER,grant(engagement,max_steps=4))
    assert error.value.status_code==403
    assert not jobs.commands

@pytest.mark.asyncio
async def test_policy_change_while_model_is_answering_disallows_finish_run(setup,engagement,monkeypatch):
    runner,jobs,gateway=setup
    policy={'status':'active','revision':'test-policy-v1',
        'enabled_profiles':('http-headers','tcp-connect'),'max_steps':16,'max_minutes':30}
    monkeypatch.setattr(runner.policy,'current',lambda:dict(policy))
    async def revoke_during_inference(route,messages,tools):
        policy['revision']='revoked-by-admin'
        return finish('solved','All done','None')
    monkeypatch.setattr(gateway,'complete',revoke_during_inference)
    ended=await settle(runner.store,runner,runner.start(OWNER,grant(engagement))['id'])
    assert ended['status']=='blocked'
    assert not jobs.commands
    assert 'policy' in ended['summary'].lower()

@pytest.mark.asyncio
async def test_rabbit_looks_up_unfamiliar_tool_docs_without_execution(setup,engagement):
    runner,jobs,gateway=setup
    looked=[]
    class Docs:
        def get(self,name,owner=None):
            looked.append(name)
            return {'name':name,'documents':[{'source':'local','excerpt':'--version usage','trust':'untrusted-reference'}],
                    'flags':['--version'],'execution_authorized':False}
    runner.knowledge=Docs()
    gateway.replies=[{'content':'','calls':[{'id':'c1','name':'inspect_tool','arguments':json.dumps({'name':'foo-tool'})}]},
                     finish('blocked','No allowed workflows were useful','Review manually')]
    finished=await settle(runner.store,runner,runner.start(OWNER,grant(engagement))['id'])
    assert finished['status']=='blocked'
    assert looked==['foo-tool']
    assert not jobs.commands
    assert any('documentation' in str(msg[1]).lower() for msg in gateway.requests[1:])

def test_read_only_documentation_accepts_case_sensitive_installed_executable_names():
    from foxworx.rabbit import _decision
    for name in ('theHarvester','httpx-toolkit','enum4linux-ng','python3.13'):
        answer={'content':'','calls':[{'id':'c1','name':'inspect_tool','arguments':json.dumps({'name':name})}]}
        action,data=_decision(answer)
        assert action=='inspect_tool' and data['name']==name
