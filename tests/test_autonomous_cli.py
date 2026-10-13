"""Delegated CLI jobs remain attached to a finite, revocable operator grant."""
import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from foxworx.adapters import AdapterPolicy, parse_document
from foxworx.jobs import JobManager
from foxworx.models import RabbitSpec, ProposalSpec
from foxworx.rabbit import RabbitRunner
from foxworx.registry import Registry

OWNER='local-operator'

def policy_document(**updates):
    return {'schema':3,'enabled_profiles':[],'registered_adapters':[],
            'allow_installed_cli':True,'max_steps':256,'max_minutes':240,**updates}

def test_new_policy_and_legacy_permissions():
    value=parse_document(json.dumps(policy_document()).encode())
    assert value['allow_installed_cli'] and value['max_steps']==256
    old=parse_document(json.dumps({'schema':1,'enabled_profiles':['dns-a'],'max_steps':8,'max_minutes':15}).encode())
    assert not old['allow_installed_cli']
    for updates in ({'allow_installed_cli':'yes'},{'max_steps':10001},{'max_minutes':1441}):
        with pytest.raises(ValueError):parse_document(json.dumps(policy_document(**updates)).encode())


def test_run_modes_keep_legacy_defaults_and_require_valid_grants():
    spec=RabbitSpec(engagement_id='lab',objective='Inspect the local test',target='127.0.0.1',execution_mode='installed_cli',authorized=True)
    assert spec.profiles==[] and spec.max_steps==64 and spec.max_minutes==60
    old=RabbitSpec(engagement_id='lab',objective='Inspect the local test',target='127.0.0.1',profiles=['dns-a'])
    assert old.execution_mode=='workflows' and old.max_steps==8 and old.max_minutes==15
    with pytest.raises(ValidationError):RabbitSpec(engagement_id='lab',objective='Inspect the local test',target='127.0.0.1')


def action(function_name,**args):return {'content':'','calls':[{'id':'a','name':function_name,'arguments':json.dumps(args)}]}

def finish():return action('finish_run',status='solved',summary='Verified fixture output',next_steps='Review saved evidence')

class Gateway:
    def __init__(self,replies):self.replies=list(replies);self.requests=[]
    async def complete(self,route,messages,tools):
        self.requests.append((messages,tools))
        return self.replies.pop(0) if self.replies else finish()

@pytest.fixture
def setup_cli(cfg,store,engagement,tmp_path,monkeypatch):
    tools=tmp_path/'bin';tools.mkdir()
    for name,body in [('fixture-fail','echo deliberate-failure; exit 1'),('fixture-good','echo confirmed-result')]:
        path=tools/name;path.write_text('#!/bin/sh\n'+body+'\n');path.chmod(0o700)
    cfg.extra_paths=(str(tools),)
    registry=Registry(cfg);registry.scan()
    manager=JobManager(cfg,store,registry)
    state={'status':'active','revision':'trusted','registered_adapters':{},'enabled_profiles':(),
           'allow_installed_cli':True,'max_steps':256,'max_minutes':240}
    monkeypatch.setattr(AdapterPolicy,'current',lambda self:dict(state))
    gateway=Gateway([])
    providers=SimpleNamespace(resolve=lambda owner:{'provider':'ollama','model_id':'fixture'})
    runner=RabbitRunner(cfg,store,manager,providers,gateway)
    spec=dict(engagement_id=engagement['id'],objective='Inspect local fixture output',target='127.0.0.1',
              execution_mode='installed_cli',max_steps=6,max_minutes=1,authorized=True)
    return runner,manager,gateway,state,spec

async def settle(runner,rid):
    for _ in range(500):
        record=runner.get(OWNER,rid)
        if record['status'] not in ('queued','running','stopping'):return record
        await asyncio.sleep(.01)
    pytest.fail('Run did not finish')

@pytest.mark.asyncio
async def test_automatic_failure_then_alternative_records_delegation(setup_cli,store):
    runner,jobs,gateway,_,spec=setup_cli
    gateway.replies=[action('run_tool',name='fixture-fail',args=[],reason='First attempt'),
                     action('run_tool',name='fixture-good',args=[],reason='Try another installed tool'),finish()]
    started=runner.start(OWNER,RabbitSpec(**spec))
    result=await settle(runner,started['id'])
    assert result['status']=='solved',result
    assert [s['status'] for s in result['steps']]==['failed','succeeded']
    saved=[store.get('job',s['job_id'],OWNER) for s in result['steps']]
    assert all(j['run_id']==started['id'] for j in saved)
    assert 'confirmed-result' in jobs.output(saved[-1]['id'],OWNER)['text']

@pytest.mark.asyncio
async def test_legacy_grant_cannot_execute_cli(setup_cli):
    runner,_,gateway,policy,spec=setup_cli
    policy['enabled_profiles']=('dns-a',)
    spec.update(execution_mode='workflows',profiles=['dns-a'])
    gateway.replies=[action('run_tool',name='fixture-good',args=[],reason='Not authorized'),finish()]
    result=await settle(runner,runner.start(OWNER,RabbitSpec(**spec))['id'])
    assert not any(s.get('job_id') for s in result['steps'])
    assert result['status']=='blocked'

@pytest.mark.asyncio
async def test_followup_during_inference_discards_old_action(setup_cli):
    runner,_,gateway,_,spec=setup_cli
    entered=asyncio.Event();release=asyncio.Event();requests=[]
    async def complete(route,messages,tools):
        requests.append(messages)
        if len(requests)==1:
            entered.set();await release.wait()
            return action('run_tool',name='fixture-fail',args=[],reason='Old instruction')
        if len(requests)==2:return action('run_tool',name='fixture-good',args=[],reason='New instruction')
        return finish()
    gateway.complete=complete
    started=runner.start(OWNER,RabbitSpec(**spec));await entered.wait()
    assert hasattr(runner,'add_message'), 'Supplemental instruction handling is missing'
    runner.add_message(OWNER,started['id'],'Use the successful fixture instead')
    release.set();result=await settle(runner,started['id'])
    assert result['status']=='solved'
    assert len([s for s in result['steps'] if s.get('job_id')])==1
    assert result['messages'][0]['applied_revision']==1
    assert result['decisions_used']==3
    assert result['budget_end']==started['budget_end']
    assert 'Use the successful fixture instead' in json.dumps(requests[1])

@pytest.mark.asyncio
async def test_stop_during_inference_never_launches(setup_cli):
    runner,_,gateway,_,spec=setup_cli
    entered=asyncio.Event()
    async def complete(*args):
        entered.set();await asyncio.sleep(20)
        return action('run_tool',name='fixture-good',args=[],reason='Too late')
    gateway.complete=complete
    run=runner.start(OWNER,RabbitSpec(**spec));await entered.wait()
    final=await runner.stop(OWNER,run['id'])
    assert final['status']=='stopped' and not any(s.get('job_id') for s in final['steps'])

@pytest.mark.asyncio
async def test_identical_failures_are_not_repeated_forever(setup_cli):
    runner,_,gateway,_,spec=setup_cli
    gateway.replies=[action('run_tool',name='fixture-fail',args=[],reason='Try')]*4
    result=await settle(runner,runner.start(OWNER,RabbitSpec(**spec))['id'])
    assert len([s for s in result['steps'] if s.get('job_id')])==2
    assert result['status']=='blocked'

@pytest.mark.asyncio
@pytest.mark.parametrize('change',['stop','policy','executable','scope','instructions'])
async def test_queued_job_rechecks_grant_before_process_launch(setup_cli,store,engagement,change):
    runner,jobs,_,policy,spec=setup_cli
    from foxworx.jobs import scope_stamp
    record=store.put('rabbit',OWNER,{**spec,'profiles':[],'status':'running','policy_revision':'trusted',
        'authorization_stamp':scope_stamp(engagement),'instruction_revision':0,'decisions_used':1,
        'budget_end':time.time()+60,'messages':[]})
    proposal=jobs.prepare(OWNER,ProposalSpec(engagement_id=engagement['id'],tool='fixture-good',
        profile='advanced',target='127.0.0.1',args=[],reason='Delegated fixture'),source='rabbit-hole')
    proposal=jobs.delegate(OWNER,proposal,record['id'],0)
    job=await jobs.approve(OWNER,proposal['id'],proposal['digest'],True)
    # approve schedules its worker; these mutations happen before the worker runs.
    if change=='stop':
        record['status']='stopped';store.put('rabbit',OWNER,record)
    elif change=='policy':policy['revision']='revoked'
    elif change=='instructions':
        record['instruction_revision']=1;store.put('rabbit',OWNER,record)
    elif change=='scope':
        engagement['exclude']=['127.0.0.1'];store.put('engagement',OWNER,engagement)
    else:
        from pathlib import Path
        Path(proposal['argv'][0]).write_text('#!/bin/sh\necho CHANGED\n')
    for _ in range(100):
        result=store.get('job',job['id'],OWNER)
        if result['status'] not in ('queued','running'):break
        await asyncio.sleep(.01)
    assert result['status']=='failed' and result.get('pid') is None
    assert result['output_bytes']==0

@pytest.mark.asyncio
async def test_policy_revocation_during_running_job_stops_process(setup_cli,store):
    runner,jobs,gateway,policy,spec=setup_cli
    from pathlib import Path
    tool=Path(jobs.registry.resolve('fixture-good')['path'])
    tool.write_text('#!/bin/sh\necho started\nsleep 10\n')
    gateway.replies=[action('run_tool',name='fixture-good',args=[],reason='Wait on fixture')]
    run=runner.start(OWNER,RabbitSpec(**spec))
    for _ in range(200):
        if runner.active_jobs:break
        await asyncio.sleep(.01)
    policy['revision']='revoked'
    result=await settle(runner,run['id'])
    assert result['status']=='blocked' and 'policy' in result['summary'].lower()
    jid=result['steps'][0]['job_id']
    for _ in range(100):
        job=store.get('job',jid,OWNER)
        if job['status'] not in ('running','queued','stopping'):break
        await asyncio.sleep(.01)
    assert job['status']=='stopped'


def test_message_endpoint_requires_identity_integrity_and_active_run(cfg):
    from fastapi.testclient import TestClient
    from foxworx.app import create_app
    app=create_app(cfg,_allow_root_for_tests=True)
    run=app.state.store.put('rabbit',OWNER,{'status':'running','messages':[],'instruction_revision':0})
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50123)) as client:
        url=f"/api/rabbit-runs/{run['id']}/messages"
        assert client.post(url,json={'message':'Use another tool'},headers={'Origin':cfg.origin}).status_code==401
        assert client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        assert client.post(url,json={'message':'Use another tool'}).status_code==403
        csrf=client.get('/api/session').json()['csrf']
        headers={'Origin':cfg.origin,'X-Foxworx-CSRF':csrf}
        assert client.post(url,json={'message':' '},headers=headers).status_code==422
        # Startup recovery interrupted the synthetic running record.
        assert client.post(url,json={'message':'Use another tool'},headers=headers).status_code==409
        run['status']='running';app.state.store.put('rabbit',OWNER,run)
        result=client.post(url,json={'message':'Use another tool'},headers=headers)
        assert result.status_code==200 and result.json()['instruction_revision']==1
        foreign=app.state.store.put('rabbit','someone-else',{'status':'running','messages':[],'instruction_revision':0})
        assert client.post(f"/api/rabbit-runs/{foreign['id']}/messages",json={'message':'No'},headers=headers).status_code==404

@pytest.mark.asyncio
async def test_all_accepted_followups_reach_subsequent_decisions(setup_cli):
    runner,_,gateway,_,spec=setup_cli
    entered=asyncio.Event();release=asyncio.Event();requests=[]
    async def complete(route,messages,tools):
        requests.append(messages)
        if len(requests)==1:
            entered.set();await release.wait()
            return action('run_tool',name='fixture-fail',args=[],reason='Outdated')
        if len(requests)==2:return action('run_tool',name='fixture-good',args=[],reason='Use updated instructions')
        return finish()
    gateway.complete=complete
    run=runner.start(OWNER,RabbitSpec(**spec));await entered.wait()
    for i in range(10):runner.add_message(OWNER,run['id'],f'Operator directive number {i:02d}')
    release.set();record=await settle(runner,run['id'])
    assert record['status']=='solved'
    for request in requests[1:]:
        context=json.loads(request[1]['content'].split('\n',1)[1])
        assert len(context['supplemental_operator_instructions'])==10
        assert context['supplemental_operator_instructions'][0]['message']=='Operator directive number 00'
    assert all(m['applied_revision']==10 for m in record['messages'])

@pytest.mark.asyncio
async def test_time_budget_expiry_during_final_inference_cannot_report_success(setup_cli,monkeypatch):
    runner,_,gateway,_,spec=setup_cli
    import foxworx.rabbit as rabbit_module
    real_time=time.time;offset=[0];calls=[]
    monkeypatch.setattr(rabbit_module.time,'time',lambda:real_time()+offset[0])
    async def complete(*args):
        calls.append(True)
        if len(calls)==1:return action('run_tool',name='fixture-good',args=[],reason='Get fixture result')
        offset[0]=70
        return finish()
    gateway.complete=complete
    result=await settle(runner,runner.start(OWNER,RabbitSpec(**spec))['id'])
    assert result['status']=='blocked' and 'time budget' in result['summary']
