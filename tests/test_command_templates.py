"""The model can select parameters, never arbitrary execution syntax."""
import pytest
from foxworx.command_templates import validate_template, compile_template, validate_library
from foxworx.adapters import parse_document, PolicyError

BASE = {'id':'probe-http','tool':'curl','label':'HTTP probe','hint':'Lab HTTP check',
        'target_kind':'url','risk':'recon','mode':'autonomous',
        'argv':['--max-time','10','--head','{target}','--retry','{param:attempts}','--http1.1','{param:proto}'],
        'parameters':{'attempts':{'type':'integer','min':0,'max':2,'default':0},
                      'proto':{'type':'enum','choices':['--compressed','--silent'],'default':'--silent'}}}

def test_compiler_uses_explicit_argv_no_shell():
    adapter=validate_template(BASE)
    assert compile_template(adapter,'https://example.org/',{'attempts':2,'proto':'--silent'}) == ['--max-time','10','--head','https://example.org/','--retry','2','--http1.1','--silent']
    with pytest.raises(ValueError): compile_template(adapter,'example.org',{})
    with pytest.raises(ValueError): compile_template(adapter,'https://example.org/',{'attempts':999})
    with pytest.raises(ValueError): compile_template(adapter,'https://example.org/',{'proto':'--location'})
    with pytest.raises(ValueError): compile_template(adapter,'https://example.org/',{'attempts':1,'unknown':1})

def test_template_rejects_runtime_escape_routes():
    bad=[
        {'argv':['bash','-c','{param:x}']},
        {'tool':'bash'}, {'tool':'python3'}, {'tool':'sudo'},
        {'argv':['{param:x}','{target}']},
        {'argv':['--url','https://different.example/']},
        {'argv':['-o','/tmp/output','{target}']},
        {'argv':['--', '{target}','{target}']},
        {'parameters':{'x':{'type':'string'}}},
        {'mode':'autonomous','risk':'intrusive'},
        {'argv':['--flag={param:attempts}','{target}']},
        {'id':'tcp-connect'},
        {'argv':['-w','/tmp/input.txt','{target}']},
        {'argv':['--script','{target}']},
    ]
    for mutation in bad:
        with pytest.raises(ValueError): validate_template({**BASE,**mutation})

def test_registered_templates_fit_schema_2_and_old_schema_1_still_valid():
    v1={'schema':1,'enabled_profiles':['dns-a'],'max_steps':4,'max_minutes':5}
    assert parse_document(__import__('json').dumps(v1).encode())['registered_adapters']=={}
    v2={'schema':2,'enabled_profiles':['dns-a','probe-http'],'max_steps':4,'max_minutes':5,'registered_adapters':[BASE]}
    parsed=parse_document(__import__('json').dumps(v2).encode())
    assert 'probe-http' in parsed['registered_adapters']
    with pytest.raises(PolicyError): parse_document(__import__('json').dumps({**v2,'enabled_profiles':['missing']}).encode())

def test_curated_library_is_validated():
    library=validate_library()
    assert len(library)>=15
    assert 'nuclei-review' in library
    assert 'ffuf-small' in library
    assert 'sqlmap-review' in library
    assert 'metasploit-version' not in library  # interactive exploitation console is terminal-only
    assert library['sqlmap-review']['mode']=='review'
    assert library['ffuf-small']['mode']=='autonomous'

def test_job_manager_prepares_registered_adapter_without_raw_model_argv(cfg,store,monkeypatch):
    from foxworx.jobs import JobManager
    from foxworx.registry import Registry
    from foxworx.adapters import AdapterPolicy
    from foxworx.store import identifier
    from fastapi import HTTPException
    import shutil
    jobs=JobManager(cfg,store,Registry(cfg))
    owner='local-operator'
    eng=store.put('engagement',owner,{'name':'local','include':['127.0.0.1'],'exclude':[],'notes':''})
    adapter={**BASE,'target_kind':'url','argv':['--head','{target}'] ,'parameters':{}}
    trusted={'status':'active','revision':'rev-1','enabled_profiles':('probe-http',),'registered_adapters':{'probe-http':adapter},'max_steps':5,'max_minutes':5}
    monkeypatch.setattr(AdapterPolicy,'current',lambda self:trusted)
    result=jobs.prepare_registered(owner,eng['id'],adapter,'http://127.0.0.1/',{},'Review a header check','rev-1','adapter-preview')
    assert result['profile']=='probe-http'
    assert result['argv'][1:]==['--head','http://127.0.0.1/']
    assert result['scope_check']=='admin-template-input-checked'
    with pytest.raises(HTTPException) as err:
        jobs.prepare_registered(owner,eng['id'],adapter,'http://192.0.2.1/',{},'Scope escape','rev-1','adapter-preview')
    assert err.value.status_code==403
    trusted['revision']='rev-2'
    import asyncio
    with pytest.raises(HTTPException): asyncio.run(jobs.approve(owner,result['id'],result['digest'],True))

@pytest.mark.asyncio
async def test_rabbit_runner_supports_registered_templates_with_typed_values(cfg,store,monkeypatch):
    from foxworx.rabbit import RabbitRunner
    from foxworx.adapters import AdapterPolicy
    from foxworx.models import RabbitSpec
    from tests.test_rabbit import StubJobs, FakeGateway, FakeProviders, settle, finish
    # Stub adapter runner so we can inspect the parameter contract without executing a CLI.
    owner='local-operator'
    eng=store.put('engagement',owner,{'name':'lab','include':['127.0.0.1'],'exclude':[],'notes':''})
    jobs=StubJobs(eng)
    invoked=[]
    def prepare_registered(owner,engagement_id,adapter,target,parameters,reason,revision,source):
        invoked.append((adapter['id'],parameters,target,source));return {'id':'prepared','digest':'a'*64}
    jobs.prepare_registered=prepare_registered
    from unittest.mock import AsyncMock
    gateway=FakeGateway([{'content':'','calls':[{'name':'choose_workflow','arguments':__import__('json').dumps({'profile':'probe-http','reason':'Inspect','parameters':{'attempts':1}})}]},finish('solved')])
    runner=RabbitRunner(cfg,store,jobs,FakeProviders(),gateway)
    adapter={**BASE,'target_kind':'host','argv':['--head','{target}','--retry','{param:attempts}'],'parameters':{'attempts':{'type':'integer','min':0,'max':2,'default':0}}}
    monkeypatch.setattr(AdapterPolicy,'current',lambda self:{'status':'active','revision':'rev-v2',
        'enabled_profiles':('probe-http',),'registered_adapters':{'probe-http':adapter},'max_steps':5,'max_minutes':5})
    async def waiting(owner,jid,deadline,run_id):return {'status':'succeeded','returncode':0,'output_bytes':0}
    monkeypatch.setattr(runner,'_wait_job',waiting)
    spec=RabbitSpec(engagement_id=eng['id'],objective='Inspect an authorized local lab',target='127.0.0.1',profiles=['probe-http'],max_steps=4,max_minutes=1,authorized=True)
    result=runner.start(owner,spec)
    ended=await settle(store,runner,result['id'])
    assert ended['status']=='solved'
    assert invoked==[('probe-http',{'attempts':1},'127.0.0.1','rabbit-hole')]


def test_registered_adapter_api_creates_only_approval_preview(cfg,monkeypatch):
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    from foxworx.adapters import AdapterPolicy
    from fastapi import HTTPException
    adapter={**BASE,'target_kind':'url','argv':['--head','{target}'],'parameters':{}}
    state={'status':'active','revision':'rev-v2','enabled_profiles':('probe-http',),
           'registered_adapters':{'probe-http':adapter},'max_steps':5,'max_minutes':5}
    monkeypatch.setattr(AdapterPolicy,'current',lambda self:state)
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',49998)) as client:
        unauth={'engagement_id':'x'*24,'profile':'probe-http','target':'http://127.0.0.1/','parameters':{},'reason':'Preview'}
        assert client.post('/api/registered-proposals',json=unauth).status_code in (401,403)
        client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin})
        csrf=client.get('/api/session').json()['csrf']
        client.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':csrf})
        eng=client.get('/api/engagements').json()[0]
        payload={'engagement_id':eng['id'],'profile':'probe-http','target':'http://127.0.0.1/','parameters':{},'reason':'Preview'}
        response=client.post('/api/registered-proposals',json=payload)
        assert response.status_code==200,response.text
        assert response.json()['status']=='pending'
        assert not client.get('/api/jobs').json()
        state['revision']='rev-3'
        p=response.json()
        assert client.post(f"/api/proposals/{p['id']}/approve",json={'digest':p['digest'],'authorized':True}).status_code==409

@pytest.mark.asyncio
async def test_copilot_generates_registered_review_proposal_not_execution(cfg,store,monkeypatch):
    from foxworx.ai import Copilot
    from foxworx.registry import Registry
    from foxworx.jobs import JobManager
    from foxworx.adapters import AdapterPolicy
    from foxworx.models import ChatSpec
    from foxworx.providers import ProviderManager
    from foxworx.model_gateway import ModelGateway
    adapter={**BASE,'target_kind':'url','mode':'review','risk':'intrusive','argv':['--head','{target}'],'parameters':{}}
    monkeypatch.setattr(AdapterPolicy,'current',lambda self:{'status':'active','revision':'rev1','enabled_profiles':('probe-http',),'registered_adapters':{'probe-http':adapter},'max_steps':4,'max_minutes':4})
    cfg.api_key='demo';cfg.model='demo'
    copilot=Copilot(cfg,store,Registry(cfg),JobManager(cfg,store,Registry(cfg)), providers=ProviderManager(cfg,store))
    eng=store.put('engagement','local-operator',{'name':'lab','include':['127.0.0.1'],'exclude':[],'notes':''})
    async def fake(**kw):
        assert any(t['function']['name']=='propose_registered_adapter' for t in kw.get('tools',[]))
        return {'choices':[{'message':{'content':'Review this registered command',
            'tool_calls':[{'type':'function','id':'c1','function':{'name':'propose_registered_adapter','arguments':__import__('json').dumps({'profile':'probe-http','target':'http://127.0.0.1/','parameters':{},'reason':'Safe preview'})}}]}}]}
    copilot.gateway=ModelGateway(completion=fake)
    response=await copilot.chat('local-operator',ChatSpec(engagement_id=eng['id'],message='Prepare the registered tool for inspection'))
    assert len(response['proposals'])==1
    assert response['proposals'][0]['adapter_id']=='probe-http'
    assert not copilot.store.list('job','local-operator')

def test_intrusive_binary_cannot_be_mislabeled_autonomous():
    for tool in ('sqlmap','masscan','nuclei','nikto','wapiti','msfconsole','hydra'):
        with pytest.raises(ValueError):
            validate_template({**BASE,'tool':tool,'risk':'recon','mode':'autonomous'})


def test_encoded_dangerous_flags_and_arbitrary_enum_values_fail_closed():
    for args in (['--output=/tmp/findings','{target}'], ['--script=evil.nse','{target}'],
                 ['--config=/tmp/custom','{target}']):
        with pytest.raises(ValueError): validate_template({**BASE,'argv':args,'parameters':{}})
    with pytest.raises(ValueError):
        validate_template({**BASE,'parameters':{'attempts':{'type':'enum','choices':['--silent','--location'],'default':'--silent'},'proto':BASE['parameters']['proto']}})


def test_unreviewed_autonomous_executables_are_not_delegated():
    """A root JSON policy cannot turn a destructive CLI into autonomous agent power."""
    from foxworx.command_templates import validate_template
    base={
        'id':'generic-inventory', 'tool':'curl', 'label':'Example',
        'hint':'Bounded example target', 'target_kind':'url',
        'risk':'recon', 'mode':'autonomous', 'argv':['--head','{target}'], 'parameters':{}
    }
    assert validate_template(base)['mode']=='autonomous'
    for executable in ('rm', 'chmod', 'dd', 'apt-get', 'msfconsole', 'sqlmap', 'masscan'):
        with pytest.raises(ValueError):
            validate_template({**base,'tool':executable})
    # Other noninteractive executables may still be registered for per-command review.
    assert validate_template({**base,'tool':'sqlmap','risk':'intrusive','mode':'review'})['mode']=='review'
