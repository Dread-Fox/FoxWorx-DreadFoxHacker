import pytest
from fastapi import HTTPException
from foxworx.model_gateway import ModelGateway, make_tools

@pytest.mark.asyncio
async def test_gateway_normalizes_cloud_and_local_calls():
    seen=[]
    async def fake(**kw):
        seen.append(kw)
        return {'choices':[{'message':{'content':'Ready','tool_calls':[]}}]}
    gateway=ModelGateway(completion=fake)
    for provider,model,base in [('anthropic','anthropic/claude-demo',''),('ollama','ollama_chat/qwen3','http://127.0.0.1:11434')]:
        out=await gateway.complete({'provider':provider,'model':model,'api_key':'test-key' if provider=='anthropic' else '', 'api_base':base},[{'role':'user','content':'Hi'}],tools=[])
        assert out['content']=='Ready' and out['calls']==[]
    assert seen[0]['model']=='anthropic/claude-demo' and seen[0]['api_key']=='test-key'
    assert seen[1]['api_base']=='http://127.0.0.1:11434'
    assert 'tools' not in seen[1]

@pytest.mark.asyncio
async def test_gateway_parses_tool_calls_without_running_anything():
    async def fake(**kw):
        assert kw['tools'][0]['function']['name']=='lookup_tools'
        return {'choices':[{'message':{'content':None, 'tool_calls':[{'id':'call1','type':'function','function':{'name':'lookup_tools','arguments':'{"query":"nmap"}'}}]}}]}
    out=await ModelGateway(completion=fake).complete({'provider':'openai','model':'openai/gpt-4o','api_key':'test','api_base':''},[{'role':'user','content':'Hi'}],tools=make_tools())
    assert out['calls'][0]['name']=='lookup_tools' and out['calls'][0]['id']=='call1'

@pytest.mark.asyncio
async def test_gateway_never_leaks_provider_error_or_key():
    async def fake(**kw):
        raise RuntimeError('bad sk-private-key value from provider')
    with pytest.raises(HTTPException) as error:
        await ModelGateway(completion=fake).complete({'provider':'openai','model':'openai/example','api_key':'sk-private-key','api_base':''},[{'role':'user','content':'Hello'}],tools=[])
    assert 'sk-private-key' not in error.value.detail
    assert error.value.status_code==502

@pytest.mark.asyncio
async def test_gateway_rejects_malformed_response():
    async def fake(**kw):return {'choices':[]}
    with pytest.raises(HTTPException):
        await ModelGateway(completion=fake).complete({'provider':'openai','model':'openai/example','api_key':'test','api_base':''},[{'role':'user','content':'Hi'}],tools=[])

@pytest.mark.asyncio
async def test_local_compatible_api_never_inherits_cloud_key():
    captured=[]
    async def fake(**kw):
        captured.append(kw)
        return {'choices':[{'message':{'content':'OK','tool_calls':[]}}]}
    await ModelGateway(completion=fake).complete({'provider':'lmstudio','model':'openai/local-model',
        'api_base':'http://127.0.0.1:1234/v1','api_key':''},[{'role':'user','content':'Hi'}],[])
    assert captured[0]['api_key']=='foxworx-local-no-secret'
