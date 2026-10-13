"""DreadFox can discuss coarse workbench pulse, never operational contents."""
import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from foxworx.pet import DreadFoxPet
from foxworx.pet_chat import DreadFoxConversation
from foxworx.app import create_app

class Provider:
    def resolve(self, owner):
        return {'provider':'ollama', 'model_id':'local-model', 'api_base':'http://127.0.0.1:11434', 'api_key':''}

class Gateway:
    def __init__(self): self.calls=[]
    async def complete(self, route, messages, tools):
        self.calls.append((route,messages,tools))
        return {'content':'A little progress adds up.', 'calls':[]}


def test_pulse_default_off_no_backfill_or_sensitive_details(store):
    now=1_800_000_000
    pet=DreadFoxPet(store,clock=lambda:now)
    pet.hatch('alice')
    assert pet.operations('alice')['enabled'] is False
    pet.process_event('alice','job-succeeded',now,details='SECRET cmd https://private-target.example')
    assert pet.operations('alice')['signals']==[]
    view=pet.set_operations('alice',True)
    assert view['enabled'] and view['signals']==[]
    pet.process_event('alice','job-succeeded',now+65,details='SECRET cmd https://private-target.example')
    pulse=pet.operations('alice')
    assert any(x['area']=='completed_jobs' for x in pulse['signals'])
    assert 'SECRET' not in json.dumps(pulse)
    with store.db() as db:
        entries=db.execute('SELECT * FROM pet_operation_days').fetchall()
    assert 'SECRET' not in str([dict(x) for x in entries])
    assert set(dict(entries[0]))=={'owner','pet_id','day','area','count'}


def test_pulse_records_failures_without_xp_and_caps_counts(store):
    now=1_800_000_000
    pet=DreadFoxPet(store,clock=lambda:now)
    pet.hatch('alice');pet.set_operations('alice',True)
    for i in range(150):
        pet.process_event('alice','job-failed',now+1+i,details='private-host')
    result=pet.operations('alice')
    assert result['signals']==[{'area':'unfinished_jobs','level':'frequent'}]
    with store.db() as db:
        cnt=db.execute('SELECT count FROM pet_operation_days WHERE owner=?',('alice',)).fetchone()[0]
    assert cnt<=20
    assert pet.snapshot('alice')['xp']==0


def test_pulse_owner_tracking_retention_erasure_and_generation(store):
    t=1_800_000_000
    pet=DreadFoxPet(store,clock=lambda:t)
    pet.hatch('alice');pet.hatch('bob')
    pet.set_operations('alice',True)
    pet.process_event('alice','terminal-created',t)
    assert pet.operations('bob')['signals']==[]
    assert pet.operations('alice')['signals']
    pet.tracking('alice',False)
    assert pet.operations('alice')['signals']==[]  # paused tracking never shares pulse
    assert pet.process_event('alice','job-succeeded',t+100) is False
    pet.tracking('alice',True)
    assert pet.operations('alice')['signals']
    pet.clear_operations('alice')
    assert pet.operations('alice')['enabled'] is False
    assert pet.operations('alice')['signals']==[]
    pet.set_operations('alice',True)
    pet.process_event('alice','terminal-created',t+101)
    assert pet.operations('alice',at=t+8*86400)['signals']==[]
    pet.delete('alice');pet.hatch('alice')
    assert pet.operations('alice')['enabled'] is False
    with store.db() as db:
        assert db.execute('SELECT COUNT(*) FROM pet_operation_days WHERE owner=?',('alice',)).fetchone()[0]==0


@pytest.mark.asyncio
async def test_ai_context_opt_in_only_whitelist_and_no_tools(store):
    t=1_800_000_000
    pet=DreadFoxPet(store,clock=lambda:t);pet.hatch('alice')
    p=Provider();g=Gateway();chat=DreadFoxConversation(pet,p,g)
    chat.set_mode('alice','ai')
    pet.process_event('alice','job-succeeded',t,details='PRIVATE-ADDRESS token=DO-NOT-LEAK')
    await chat.reply('alice','How was our week?')
    state=json.loads(g.calls[-1][1][0]['content'].split('SAFE PET STATE (data): ',1)[1])
    assert 'recent_workbench_pulse' not in state
    pet.set_operations('alice',True)
    pet.process_event('alice','job-succeeded',t+100,details='PRIVATE-ADDRESS token=DO-NOT-LEAK')
    await chat.reply('alice','What have we done?')
    system=g.calls[-1][1][0]['content']
    state=json.loads(system.split('SAFE PET STATE (data): ',1)[1])
    assert 'recent_workbench_pulse' in state
    assert state['recent_workbench_pulse']['signals']==[{'area':'completed_jobs','level':'some'}]
    assert 'PRIVATE-ADDRESS' not in json.dumps(g.calls[-1])
    assert g.calls[-1][2]==[]
    pet.set_operations('alice',False)
    await chat.reply('alice','What are you up to?')
    state=json.loads(g.calls[-1][1][0]['content'].split('SAFE PET STATE (data): ',1)[1])
    assert 'recent_workbench_pulse' not in state


@pytest.mark.asyncio
async def test_offline_workbench_conversation_only_with_optin(store):
    now=1_800_000_000
    pet=DreadFoxPet(store,clock=lambda:now);pet.hatch('alice')
    chat=DreadFoxConversation(pet,Provider(),Gateway())
    no=await chat.reply('alice','What work have we done today?')
    assert 'enable' in no['answer'].lower()
    pet.set_operations('alice',True)
    pet.process_event('alice','job-succeeded',now)
    yes=await chat.reply('alice','What work have we done today?')
    assert 'finished' in yes['answer'].lower() or 'completed' in yes['answer'].lower()
    assert 'target' not in yes['answer'].lower()


def test_operations_http_permissions_and_csrf(cfg):
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as client:
        assert client.get('/api/pet/context').status_code==401
        assert client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        csrf=client.get('/api/session').json()['csrf']
        headers={'Origin':cfg.origin,'X-Foxworx-CSRF':csrf}
        assert client.put('/api/pet/context',json={'enabled':True},headers=headers).status_code==409
        assert client.post('/api/pet/hatch',json={},headers=headers).status_code==200
        assert client.get('/api/pet/context').json()['enabled'] is False
        assert client.put('/api/pet/context',json={'enabled':True},headers={'Origin':cfg.origin}).status_code==403
        assert client.put('/api/pet/context',json={'enabled':True},headers=headers).json()['enabled'] is True
        assert client.request('DELETE','/api/pet/context',json={},headers=headers).json()['enabled'] is False


@pytest.mark.asyncio
async def test_privacy_toggle_separates_ai_history_and_prevents_resurrected_context(store):
    t=1_800_000_000
    pet=DreadFoxPet(store,clock=lambda:t);pet.hatch('alice')
    p=Provider();g=Gateway();chat=DreadFoxConversation(pet,p,g);chat.set_mode('alice','ai')
    await chat.reply('alice','Before pulse')
    pet.set_operations('alice',True)
    pet.process_event('alice','job-succeeded',t,details='SECRET')
    await chat.reply('alice','During pulse')
    assert 'Before pulse' not in json.dumps(g.calls[-1][1])
    pet.set_operations('alice',False)
    await chat.reply('alice','After pulse')
    transcript=json.dumps(g.calls[-1][1])
    assert 'During pulse' not in transcript and 'Before pulse' not in transcript
    assert 'recent_workbench_pulse' not in transcript
    pet.set_operations('alice',True)
    await chat.reply('alice','Enabled again')
    assert 'During pulse' not in json.dumps(g.calls[-1][1])
    assert len(chat.history('alice')['messages'])==8


def test_observer_events_use_original_audit_action_only_and_no_details(cfg):
    import time
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as client:
        assert client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        headers={'Origin':cfg.origin,'X-Foxworx-CSRF':client.get('/api/session').json()['csrf']}
        assert client.post('/api/pet/hatch',json={},headers=headers).status_code==200
        client.put('/api/pet/context',json={'enabled':True},headers=headers)
        app.state.store.event('local-operator','job-failed','command: PRIVATE-HOST -p 22 TOKEN-SECRET')
        for _ in range(40):
            if client.get('/api/pet/context').json()['signals']:
                break
            time.sleep(0.025)
        payload=client.get('/api/pet/context').json()
        assert payload['signals']==[{'area':'unfinished_jobs','level':'some'}]
        assert 'PRIVATE-HOST' not in json.dumps(payload)
        with app.state.store.db() as db:
            raw=db.execute('SELECT * FROM pet_operation_days').fetchall()
        assert 'PRIVATE-HOST' not in str([dict(x) for x in raw])


@pytest.mark.asyncio
async def test_revocation_during_model_response_is_atomic_and_not_saved(store):
    t=1_800_000_000
    pet=DreadFoxPet(store,clock=lambda:t);pet.hatch('alice');pet.set_operations('alice',True)
    providers=Provider(); gateway=Gateway()
    async def midflight(route,messages,tools):
        assert 'recent_workbench_pulse' in messages[0]['content']
        pet.set_operations('alice',False)
        return {'content':'This answer was built under the old privacy setting', 'calls':[]}
    gateway.complete=midflight
    chat=DreadFoxConversation(pet,providers,gateway);chat.set_mode('alice','ai')
    with pytest.raises(Exception, match='privacy settings'):
        await chat.reply('alice','How is the workbench?')
    assert chat.history('alice')['messages']==[]
