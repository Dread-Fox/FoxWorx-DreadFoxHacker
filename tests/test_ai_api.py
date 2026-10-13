import pytest
from fastapi.testclient import TestClient
from foxworx.app import create_app

@pytest.fixture
def logged(cfg):
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',49999)) as c:
        assert c.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        csrf=c.get('/api/session').json()['csrf']
        c.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':csrf})
        yield c

def test_provider_settings_and_model_change(logged):
    r=logged.get('/api/ai/settings'); assert r.status_code==200
    providers={p['id']:p for p in r.json()['providers']}
    assert {'openai','anthropic','gemini','xai','deepseek','mistral','ollama','lmstudio','vllm','custom'} <= set(providers)
    assert not r.json()['ready']
    r=logged.put('/api/ai/settings',json={'provider':'ollama','model':'qwen3:8b','endpoint_id':'ollama-local'})
    assert r.status_code==200 and r.json()['ready']
    assert logged.get('/api/session').json()['ai_configured']
    assert logged.put('/api/ai/settings',json={'provider':'vllm','model':'qwen3','endpoint_id':'http://127.0.0.1:1234/v1'}).status_code==422
    assert logged.put('/api/ai/settings',json={'provider':'openai','model':'anthropic/claude','endpoint_id':''}).status_code==422

def test_api_keys_never_returned_and_cross_site_write_rejected(logged):
    url='/api/ai/keys/anthropic'
    assert logged.put(url,json={'api_key':'sk-sensitive-private-example'},headers={'Origin':'https://untrusted.example'}).status_code==403
    assert logged.put(url,json={'api_key':'sk-sensitive-private-example'}).status_code==200
    assert 'sk-sensitive-private-example' not in str(logged.get('/api/ai/settings').json())
    assert logged.put('/api/ai/settings',json={'provider':'anthropic','model':'claude-test','endpoint_id':''}).json()['ready']
    assert logged.request('DELETE',url,json={}).status_code==200
    assert not logged.get('/api/ai/settings').json()['ready']

def test_model_discovery_rejects_arbitrary_endpoints(logged):
    r=logged.get('/api/ai/models?provider=ollama&endpoint_id=http://127.0.0.1:22')
    assert r.status_code==422
    assert logged.get('/api/ai/models?provider=anthropic&endpoint_id=ollama-local').status_code==422

def test_local_provider_through_authenticated_chat(logged):
    from foxworx.model_gateway import ModelGateway
    ai = logged.app.state.ai
    calls=[]
    async def fake(**kw):
        calls.append(kw)
        return {'choices':[{'message':{'content':'Local inference is available', 'tool_calls':[]}}]}
    ai.gateway=ModelGateway(completion=fake)
    logged.put('/api/ai/settings',json={'provider':'ollama','model':'qwen3:8b','endpoint_id':'ollama-local'})
    eid=logged.get('/api/engagements').json()[0]['id']
    response=logged.post('/api/chat',json={'engagement_id':eid,'message':'Explain the local host'})
    assert response.status_code==200,response.text
    assert response.json()['provider']=='ollama'
    assert calls[0]['model']=='ollama_chat/qwen3:8b'
    assert not logged.app.state.jobs.tasks
