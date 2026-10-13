"""Companion conversations must never gain access to workbench operations."""
import asyncio
import json
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from foxworx.pet import DreadFoxPet
from foxworx.pet_chat import DreadFoxConversation
from foxworx.app import create_app


class FakeProviders:
    def __init__(self):
        self.provider = 'ollama'
        self.model = 'qwen3:8b'
        self.key = ''
    def resolve(self, owner):
        assert owner in ('alice','bob','local-operator')
        return {'provider':self.provider,'model_id':self.model,
                'model': 'ollama_chat/' + self.model if self.provider == 'ollama' else 'anthropic/' + self.model,
                'api_key': self.key, 'api_base':'http://127.0.0.1:11434' if self.provider=='ollama' else ''}


class FakeGateway:
    def __init__(self): self.calls=[]
    async def complete(self, route, messages, tools):
        self.calls.append((route,messages,tools))
        return {'content':'A curious fox remembers our first steps.','calls':[]}


@pytest.mark.asyncio
async def test_offline_conversation_works_without_provider_or_ai_and_is_private(store):
    pet=DreadFoxPet(store); pet.hatch('alice')
    providers=FakeProviders(); gateway=FakeGateway()
    convo=DreadFoxConversation(pet,providers,gateway)
    result=await convo.reply('alice','How many tails do you have?')
    assert 'tail' in result['answer'].lower()
    assert result['mode']=='offline' and result['provider']==''
    assert gateway.calls==[]
    assert convo.history('bob')['messages']==[]
    history=convo.history('alice')
    assert len(history['messages'])==2
    assert 'How many tails' in history['messages'][0]['text']
    assert 'How many tails' not in str(pet.snapshot('alice')['memories'])


@pytest.mark.asyncio
async def test_ai_requires_opt_in_and_provides_only_safe_context(store):
    pet=DreadFoxPet(store); pet.hatch('alice')
    providers=FakeProviders(); gateway=FakeGateway()
    convo=DreadFoxConversation(pet,providers,gateway)
    assert convo.history('alice')['mode']=='offline'
    with pytest.raises(ValueError, match='Hatch'):
        convo.set_mode('bob','ai')
    convo.set_mode('alice','ai')
    answer=await convo.reply('alice','Hello, fox!')
    assert answer['mode']=='ai' and answer['provider']=='ollama'
    route, messages, tools = gateway.calls[-1]
    assert tools == []
    blob=json.dumps(messages)
    assert 'DreadFox' in blob and 'Hello, fox!' in blob
    safe=json.loads(messages[0]['content'].split('SAFE PET STATE (data): ',1)[1])
    assert set(safe)=={'name','stage','tails','age_days','level','xp','mood','energy','bond','curiosity','affinities','personality','keepsakes','recent_safe_milestones'}
    assert 'api_key' not in blob and 'job_id' not in blob
    assert pet.snapshot('alice')['xp']==0  # chat does not farm XP


@pytest.mark.asyncio
async def test_history_never_crosses_provider_or_model(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    p=FakeProviders();g=FakeGateway();chat=DreadFoxConversation(pet,p,g)
    chat.set_mode('alice','ai')
    await chat.reply('alice','Ollama private journal')
    p.provider='anthropic';p.model='claude-sonnet-test';p.key='redacted-secret'
    await chat.reply('alice','Hello cloud fox')
    route,messages,tools=g.calls[-1]
    assert 'Ollama private journal' not in json.dumps(messages)
    assert 'Hello cloud fox' in json.dumps(messages)
    assert tools==[]
    assert chat.history('alice')['messages'][-1]['provider']=='anthropic'


@pytest.mark.asyncio
async def test_chat_model_cannot_call_tools_and_error_preserves_history(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    p=FakeProviders();g=FakeGateway();chat=DreadFoxConversation(pet,p,g)
    chat.set_mode('alice','ai')
    async def naughty(route,messages,tools):
        return {'content':'I ran an exploit','calls':[{'name':'propose_job'}]}
    g.complete=naughty
    with pytest.raises(HTTPException) as raised:
        await chat.reply('alice','Please launch the toolbox')
    assert raised.value.status_code==502
    assert chat.history('alice')['messages']==[]


@pytest.mark.asyncio
async def test_conversation_clears_with_reset_and_delete_and_cannot_restore_old_generation(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    p=FakeProviders();g=FakeGateway();chat=DreadFoxConversation(pet,p,g)
    chat.remember_focus('alice','exploration')
    await chat.reply('alice','hi')
    assert chat.history('alice')['focus']=='exploration'
    pet.delete('alice')
    assert chat.history('alice')['messages']==[]
    pet.hatch('alice')
    assert chat.history('alice')['messages']==[]
    assert chat.history('alice')['focus']=='auto'
    await chat.reply('alice','hello')
    chat.clear('alice')
    assert chat.history('alice')['messages']==[]
    assert pet.snapshot('alice')['hatched']


@pytest.mark.asyncio
async def test_chat_bounded_and_other_user_not_affected(store):
    pet=DreadFoxPet(store); pet.hatch('alice');pet.hatch('bob')
    p=FakeProviders();g=FakeGateway();chat=DreadFoxConversation(pet,p,g)
    with pytest.raises(ValueError,match='too long'):
        await chat.reply('alice','x'*1801)
    with pytest.raises(ValueError,match='empty'):
        await chat.reply('alice','   ')
    await chat.reply('alice','hello')
    await chat.reply('bob','who are you')
    chat.clear('alice')
    assert len(chat.history('bob')['messages'])==2
    assert chat.history('alice')['messages']==[]


def test_chat_api_csrf_and_access(cfg):
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as c:
        assert c.get('/api/pet/chat').status_code==401
        assert c.post('/api/pet/chat',json={'message':'hi'}).status_code==401
        assert c.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        info=c.get('/api/session').json();head={'Origin':cfg.origin,'X-Foxworx-CSRF':info['csrf']}
        assert c.post('/api/pet/chat',json={'message':'hi'},headers=head).status_code==409
        assert c.post('/api/pet/hatch',json={},headers=head).status_code==200
        assert c.get('/api/pet/chat').json()['mode']=='offline'
        assert c.post('/api/pet/chat',json={'message':'hello'},headers=head).status_code==200
        assert len(c.get('/api/pet/chat').json()['messages'])==2
        assert c.put('/api/pet/chat/focus',json={'focus':'wisdom'},headers=head).status_code==200
        assert c.put('/api/pet/chat/mode',json={'mode':'ai'},headers=head).status_code==200
        assert c.post('/api/pet/chat',json={'message':'hello'},headers=head).status_code==503  # no configured model
        assert c.request('DELETE','/api/pet/chat',json={},headers=head).status_code==200
        assert c.post('/api/pet/chat',json={'message':'hi'},headers={'Origin':cfg.origin,'X-Foxworx-CSRF':'bad'}).status_code==403


@pytest.mark.asyncio
async def test_same_model_at_different_self_hosted_server_is_not_forwarded(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    p=FakeProviders();g=FakeGateway();chat=DreadFoxConversation(pet,p,g)
    chat.set_mode('alice','ai')
    await chat.reply('alice','For the first server only')
    original=p.resolve
    p.resolve=lambda owner: {**original(owner),'api_base':'http://10.1.1.5:11434'}
    await chat.reply('alice','Hello second server')
    assert 'For the first server only' not in json.dumps(g.calls[-1][1])
    assert len(chat.history('alice')['messages'])==4


def test_authenticated_companion_model_route_never_accepts_tool_execution(cfg):
    """An actual HTTP request reaches the isolated pet gateway without job access."""
    app=create_app(cfg,_allow_root_for_tests=True)
    seen=[]
    async def completion(route,messages,tools):
        seen.append((route,messages,tools))
        return {'content':'*tail swish* I am your fox, not your scanner!','calls':[]}
    app.state.pet_chat.gateway.complete=completion
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as c:
        assert c.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        head={'Origin':cfg.origin,'X-Foxworx-CSRF':c.get('/api/session').json()['csrf']}
        c.headers.update(head)
        assert c.post('/api/pet/hatch',json={}).status_code==200
        assert c.put('/api/ai/settings',json={'provider':'ollama','model':'qwen3:8b','endpoint_id':'ollama-local'}).status_code==200
        assert c.put('/api/pet/chat/mode',json={'mode':'ai'}).status_code==200
        result=c.post('/api/pet/chat',json={'message':'What is your personality?'})
        assert result.status_code==200 and result.json()['provider']=='ollama'
        assert len(seen)==1 and seen[0][2]==[]
        assert all(x['role'] in ('system','user','assistant') for x in seen[0][1])
        assert c.get('/api/jobs').json()==[]
        assert c.get('/api/chat',params={'engagement_id':c.get('/api/engagements').json()[0]['id']}).json()==[]


@pytest.mark.asyncio
async def test_cloud_account_key_rotation_does_not_forward_previous_pet_chat(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    p=FakeProviders();p.provider='anthropic';p.model='claude-demo';p.key='private-key-one'
    g=FakeGateway();chat=DreadFoxConversation(pet,p,g)
    chat.set_mode('alice','ai')
    await chat.reply('alice','Private account one conversation')
    p.key='private-key-two'
    await chat.reply('alice','Private account two conversation')
    assert 'Private account one conversation' not in json.dumps(g.calls[-1][1])


@pytest.mark.asyncio
async def test_pet_milestone_memory_only_contains_static_notes_not_audit_details(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    pet.process_event('alice','job-succeeded',at=1_800_000_000,details='top-secret-target.example')
    p=FakeProviders();g=FakeGateway();chat=DreadFoxConversation(pet,p,g)
    chat.set_mode('alice','ai')
    await chat.reply('alice','Tell me what you remember')
    payload=json.dumps(g.calls[-1][1])
    assert 'Completed a workbench task together.' in payload
    assert 'top-secret-target.example' not in payload
