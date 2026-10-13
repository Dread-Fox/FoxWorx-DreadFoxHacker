"""Codex as an inference provider; no real accounts or model calls."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from foxworx.app import create_app
from foxworx.codex_agent import CodexAgent
from foxworx.model_gateway import ModelGateway, make_tools
from foxworx.models import AISelection, AIKeyChange, ChatSpec, RabbitSpec
from foxworx.providers import ProviderManager
from foxworx.jobs import JobManager
from foxworx.registry import Registry


class ProviderProcess:
    def __init__(self, executable, env, on_notification=None):
        self.proc = SimpleNamespace(returncode=None)
        self.on_notification = on_notification
        self.env = env
        self.commands = []
        self.connected = True
        self.finish = True
        self.replies = [json.dumps({'content': 'A helpful explanation.', 'calls': []})]

    async def start(self):
        return self

    async def stop(self):
        self.proc.returncode = 0

    async def call(self, method, params=None, timeout=20):
        self.commands.append((method, params))
        if method == 'account/read':
            return {'account': {'type': 'chatgpt', 'planType': 'plus'} if self.connected else None}
        if method == 'account/logout':
            self.connected = False
        if method == 'model/list':
            return {'data': [{'id': 'catalog-id', 'model': 'codex-test-model'}], 'nextCursor': None}
        if method == 'thread/start':
            return {'thread': {'id': 'new-thread-' + str(len(self.commands))}}
        if method == 'turn/start':
            self.on_notification({'method': 'turn/started', 'params': {
                'threadId': params['threadId'], 'turn': {'id': 'turn-test', 'status': 'inProgress'}}})
            if not self.finish:
                return {'turn': {'id': 'turn-test', 'status': 'inProgress', 'items': [], 'error': None}}
            self.on_notification({'method': 'item/completed', 'params': {
                'threadId': params['threadId'],
                'item': {'type': 'agentMessage', 'id': 'answer', 'text': self.replies.pop(0)}}})
            self.on_notification({'method': 'turn/completed', 'params': {
                'threadId': params['threadId'], 'turn': {'id': 'turn-test', 'status': 'completed'}}})
            return {'turn': {'id': 'turn-test', 'status': 'inProgress', 'items': [], 'error': None}}
        if method == 'turn/interrupt':
            if not params.get('turnId'):
                from foxworx.codex_agent import CodexProtocolError
                raise CodexProtocolError('Current protocol requires turnId')
        return {}


@pytest.fixture
def native(cfg, store, monkeypatch):
    jobs = JobManager(cfg, store, Registry(cfg))
    codex = CodexAgent(cfg, store, jobs, proc_factory=ProviderProcess)
    monkeypatch.setattr(codex, 'installed', lambda: '/fixture/codex')
    return codex


async def test_codex_selection_uses_signin_and_no_litellm(native, cfg, store, monkeypatch):
    manager = ProviderManager(cfg, store, codex=native)
    monkeypatch.setattr('foxworx.providers.importlib.util.find_spec', lambda name: None)
    result = manager.save_selection('alice', AISelection(provider='codex', model='codex-test-model'))
    assert not result['ready']
    await native.status('alice')
    result = manager.describe('alice')
    assert result['ready'] and result['engine_installed']
    row = next(p for p in result['providers'] if p['id'] == 'codex')
    assert not row['requires_key'] and row['endpoints'] == []
    route = manager.resolve('alice')
    assert route['provider'] == 'codex' and route['owner'] == 'alice'
    assert route['model_id'] == 'codex-test-model' and not route['api_key']
    assert not manager.describe('bob')['ready']
    await native.logout('alice')
    assert not manager.describe('alice')['ready']
    await native.shutdown()


def test_codex_rejects_api_keys_and_local_endpoints(native, cfg, store):
    manager = ProviderManager(cfg, store, codex=native)
    with pytest.raises(HTTPException):
        manager.set_key('alice', 'codex', AIKeyChange(api_key='do-not-use-this-key'))
    with pytest.raises(HTTPException):
        manager.save_selection('alice', AISelection(provider='codex', model='codex-test', endpoint_id='ollama-local'))
    with pytest.raises(HTTPException):
        manager.save_selection('alice', AISelection(provider='codex', model='openai/gpt-test'))


async def test_native_completion_is_stateless_and_only_returns_requested_tools(native):
    p = await native._server('alice')
    p.replies = [json.dumps({'content': '', 'calls': [{
        'name': 'lookup_tools', 'arguments': '{"query":"curl"}'}]})]
    gateway = ModelGateway(codex=native)
    result = await gateway.complete({'provider': 'codex', 'owner': 'alice', 'model_id': 'codex-test'},
                                    [{'role': 'user', 'content': 'Find curl'}], make_tools({'lookup_tools'}))
    assert result['calls'][0]['name'] == 'lookup_tools'
    assert json.loads(result['calls'][0]['arguments']) == {'query': 'curl'}
    start = next(params for method, params in p.commands if method == 'thread/start')
    assert start['ephemeral'] and start['model'] == 'codex-test'
    assert start['sandbox'] == 'read-only' and start['approvalPolicy'] == 'never'
    assert start['config']['features.shell_tool'] is False
    assert start['config']['features.multi_agent'] is False
    assert start['config']['web_search'] == 'disabled'
    turn = next(params for method, params in p.commands if method == 'turn/start')
    assert turn['outputSchema']['additionalProperties'] is False
    assert 'Find curl' in str(turn) and 'lookup_tools' in str(turn)
    assert not native.running and not native.store.list('codex-turn', 'alice')
    p.replies = [json.dumps({'content': 'Second model.', 'calls': []})]
    result = await gateway.complete({'provider': 'codex', 'owner': 'alice', 'model_id': 'other-model'},
                                    [{'role': 'user', 'content': 'New context'}], [])
    assert result['content'] == 'Second model.'
    assert not any(method == 'thread/resume' for method, _ in p.commands)
    assert 'Find curl' not in str([v for k, v in p.commands if k == 'turn/start'][-1])
    await native.shutdown()


@pytest.mark.parametrize('reply', [
    'not JSON', '{"content":42,"calls":[]}',
    '{"content":"","calls":[{"name":"approve","arguments":"{}"}]}',
    '{"content":"","calls":[{"name":"lookup_tools","arguments":"[]"}]}',
    '{"content":"","calls":[{"name":"lookup_tools","arguments":"not JSON"}]}',
])
async def test_malformed_or_unoffered_codex_actions_fail_closed(native, reply):
    p = await native._server('alice')
    p.replies = [reply]
    with pytest.raises(HTTPException) as error:
        await native.complete('alice', 'codex-test', [{'role': 'user', 'content': 'Hi'}], make_tools({'lookup_tools'}))
    assert error.value.status_code == 502
    assert not native.running and not native.jobs.tasks
    await native.shutdown()


async def test_cancellation_interrupts_native_turn_before_releasing_owner(native):
    p = await native._server('alice')
    p.finish = False
    task = asyncio.create_task(native.complete('alice', 'codex-test', [{'role': 'user', 'content': 'Hi'}], []))
    for _ in range(30):
        if any(method == 'turn/start' for method, _ in p.commands):
            break
        await asyncio.sleep(.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    interrupted = next(params for method, params in p.commands if method == 'turn/interrupt')
    assert interrupted['threadId'].startswith('new-thread-') and interrupted['turnId'] == 'turn-test'
    assert not native.running and not native.active_threads
    await native.shutdown()


async def test_repeated_cancellation_does_not_abandon_codex_cleanup(native):
    p = await native._server('alice')
    p.finish = False
    entered = asyncio.Event()
    original = p.call
    async def delayed_interrupt(method, params=None, timeout=20):
        if method == 'turn/interrupt':
            entered.set()
            await asyncio.sleep(.1)
        return await original(method, params, timeout)
    p.call = delayed_interrupt
    task = asyncio.create_task(native.complete('alice', 'codex-test', [{'role': 'user', 'content': 'Hi'}], []))
    for _ in range(30):
        if any(method == 'turn/start' for method, _ in p.commands):break
        await asyncio.sleep(.01)
    task.cancel()
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    for _ in range(30):
        if not native.running:break
        await asyncio.sleep(.01)
    assert not native.running and not native.active_threads
    assert any(method == 'turn/interrupt' and params['turnId'] == 'turn-test' for method, params in p.commands)
    await native.shutdown()


def test_legacy_codex_turn_endpoint_redirects_to_shared_modes(cfg, monkeypatch):
    monkeypatch.setattr(CodexAgent, 'installed', lambda self: None)
    app = create_app(cfg, _allow_root_for_tests=True)
    with TestClient(app, base_url=cfg.origin, client=('127.0.0.1', 50000)) as client:
        client.post('/api/login', json={'token': cfg.local_token}, headers={'Origin': cfg.origin})
        csrf = client.get('/api/session').json()['csrf']
        client.headers.update({'Origin': cfg.origin, 'X-Foxworx-CSRF': csrf})
        eid = client.get('/api/engagements').json()[0]['id']
        response = client.post('/api/codex/turn', json={'engagement_id': eid, 'message': 'Old client'})
        assert response.status_code == 410
        assert not app.state.codex.running


def test_codex_finds_standard_user_local_install(cfg, store, tmp_path, monkeypatch):
    local = tmp_path / '.local' / 'bin' / 'codex'
    local.parent.mkdir(parents=True)
    local.write_text('#!/bin/sh\nexit 0\n')
    local.chmod(0o700)
    cfg.extra_paths = ()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('foxworx.codex_agent.shutil.which', lambda name, path: None)
    codex = CodexAgent(cfg, store, JobManager(cfg, store, Registry(cfg)))
    assert codex.installed() == str(local)


async def test_simultaneous_codex_status_requests_start_one_child(native):
    starts = []
    factory = native.proc_factory
    class SlowStart(factory):
        async def start(self):
            starts.append(self)
            await asyncio.sleep(.02)
            return self
    native.proc_factory = SlowStart
    await asyncio.gather(native.status('alice'), native.status('alice'))
    assert len(starts) == 1
    await native.shutdown()


def test_unavailable_selected_codex_does_not_break_workbench_settings(cfg, monkeypatch):
    from foxworx.providers import owner_id
    monkeypatch.setattr(CodexAgent, 'installed', lambda self: '/fixture/broken-codex')
    async def unavailable(self, owner):
        raise HTTPException(503, 'Codex could not start.')
    monkeypatch.setattr(CodexAgent, 'status', unavailable)
    app = create_app(cfg, _allow_root_for_tests=True)
    app.state.store.put('ai_selection', 'local-operator', {
        'id': owner_id('local-operator', 'current'), 'provider': 'codex', 'model': 'default', 'endpoint_id': ''})
    with TestClient(app, base_url=cfg.origin, client=('127.0.0.1', 50000)) as client:
        client.post('/api/login', json={'token': cfg.local_token}, headers={'Origin': cfg.origin})
        settings = client.get('/api/ai/settings')
        assert settings.status_code == 200 and not settings.json()['ready']
        assert client.get('/api/session').status_code == 200


async def test_codex_model_catalog_returns_inference_ids(native):
    assert await native.models('alice') == ['codex-test-model']
    await native.shutdown()


async def test_codex_rabbit_decision_uses_existing_grant_and_job_handler(native, cfg, store, engagement, monkeypatch):
    from foxworx.adapters import AdapterPolicy
    from foxworx.rabbit import RabbitRunner
    from test_rabbit import StubJobs, settle
    owner = 'local-operator'
    monkeypatch.setattr(AdapterPolicy, 'current', lambda self: {
        'status': 'active', 'revision': 'fixture-policy', 'enabled_profiles': ('http-headers',),
        'max_steps': 4, 'max_minutes': 2})
    providers = ProviderManager(cfg, store, codex=native)
    providers.save_selection(owner, AISelection(provider='codex', model='codex-test'))
    p = await native._server(owner)
    p.replies = [json.dumps({'content': '', 'calls': [{
        'name': 'choose_workflow', 'arguments': json.dumps({'profile': 'http-headers', 'reason': 'Check the granted target'})}]}),
        json.dumps({'content': '', 'calls': [{'name': 'finish_run', 'arguments': json.dumps({
            'status': 'solved', 'summary': 'Reviewed local evidence.', 'next_steps': 'Read the saved job.'})}]})]
    jobs = StubJobs(engagement)
    runner = RabbitRunner(cfg, store, jobs, providers, ModelGateway(codex=native))
    async def completed_job(*args):
        return {'status': 'succeeded', 'returncode': 0}
    monkeypatch.setattr(runner, '_wait_job', completed_job)
    record = runner.start(owner, RabbitSpec(engagement_id=engagement['id'], objective='Inspect local headers',
        target='127.0.0.1', profiles=['http-headers'], max_steps=4, max_minutes=2, authorized=True))
    final = await settle(store, runner, record['id'])
    assert final['status'] == 'solved' and final['provider'] == 'codex'
    assert final['steps'][0]['profile'] == 'http-headers' and final['steps'][0]['status'] == 'succeeded'
    assert jobs.commands == ['http-headers']
    assert not runner.tasks and not native.running
    await native.shutdown()


@pytest.mark.parametrize('mode', ['tutor', 'copilot'])
async def test_codex_uses_normal_chat_and_mode_authority(native, engagement, cfg, store, mode):
    from foxworx.ai import Copilot
    owner = 'local-operator'
    providers = ProviderManager(cfg, store, codex=native)
    providers.save_selection(owner, AISelection(provider='codex', model='codex-test'))
    p = await native._server(owner)
    store.put('chat', owner, {'engagement_id': engagement['id'], 'provider': 'openai',
                             'model': 'different-model', 'role': 'user', 'text': 'OTHER-PROVIDER-SECRET'})
    store.put('codex-turn', owner, {'engagement_id': engagement['id'], 'prompt': 'LEGACY-SECRET'})
    if mode == 'copilot':
        p.replies = [json.dumps({'content': '', 'calls': [{'name': 'propose_job', 'arguments': json.dumps({
            'tool': 'python3', 'args': ['--version'], 'profile': 'advanced', 'target': '', 'reason': 'Review local version'})}]})]
    ai = Copilot(cfg, store, native.jobs.registry, native.jobs, providers=providers, gateway=ModelGateway(codex=native))
    answer = await ai.chat(owner, ChatSpec(engagement_id=engagement['id'], message='Help me', mode=mode))
    assert answer['provider'] == 'codex'
    assert len(answer['proposals']) == (1 if mode == 'copilot' else 0)
    if answer['proposals']:
        assert answer['proposals'][0]['status'] == 'pending'
    assert not store.list('job', owner) and not native.jobs.tasks
    assert store.list('chat', owner)[0]['provider'] == 'codex'
    assert 'OTHER-PROVIDER-SECRET' not in str(p.commands)
    assert 'LEGACY-SECRET' not in str(p.commands)
    await native.shutdown()


def test_codex_provider_works_through_shared_http_endpoints(cfg, monkeypatch):
    monkeypatch.setattr(CodexAgent, 'installed', lambda self: '/fixture/codex')
    app = create_app(cfg, _allow_root_for_tests=True)
    app.state.codex.proc_factory = ProviderProcess
    with TestClient(app, base_url=cfg.origin, client=('127.0.0.1', 50000)) as client:
        client.post('/api/login', json={'token': cfg.local_token}, headers={'Origin': cfg.origin})
        csrf = client.get('/api/session').json()['csrf']
        client.headers.update({'Origin': cfg.origin, 'X-Foxworx-CSRF': csrf})
        client.get('/api/codex/status')
        selected = client.put('/api/ai/settings', json={'provider': 'codex', 'model': 'codex-test'})
        assert selected.status_code == 200 and selected.json()['ready']
        assert client.get('/api/session').json()['ai_provider'] == 'codex'
        assert client.get('/api/ai/models?provider=codex').json()['models'] == ['codex-test-model']
        eid = client.get('/api/engagements').json()[0]['id']
        answer = client.post('/api/chat', json={'engagement_id': eid, 'message': 'Explain', 'mode': 'tutor'})
        assert answer.status_code == 200 and answer.json()['provider'] == 'codex'
        assert client.get('/api/chat?engagement_id=' + eid).json()[-1]['text'] == 'A helpful explanation.'
