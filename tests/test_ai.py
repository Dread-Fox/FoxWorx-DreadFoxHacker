import json
import pytest
from fastapi import HTTPException
from foxworx.ai import Copilot
from foxworx.jobs import JobManager
from foxworx.registry import Registry
from foxworx.models import ChatSpec, AISelection, AIKeyChange
from foxworx.providers import ProviderManager
from foxworx.model_gateway import ModelGateway

@pytest.fixture
def copilot(cfg,store):
    cfg.api_key='test-only-not-a-real-key'; cfg.model='test-model'
    registry=Registry(cfg); manager=JobManager(cfg,store,registry)
    return Copilot(cfg,store,registry,manager)

def proposed():
    return {'content':'', 'calls':[{'name':'propose_job','id':'call_1','arguments':json.dumps({'tool':'python3','args':['-c','print("local test")'],'profile':'advanced','target':'','reason':'Review local test'})}]}

async def test_ai_proposes_but_never_approves_or_executes(copilot,engagement):
    seen=[]
    async def fake(**kwargs):
        seen.append(kwargs)
        return {'choices':[{'message':{'content':'', 'tool_calls':[{'type':'function','id':'call_1','function':{'name':'propose_job','arguments':proposed()['calls'][0]['arguments']}}]}}]}
    copilot.gateway=ModelGateway(completion=fake)
    result=await copilot.chat('local-operator',ChatSpec(engagement_id=engagement['id'],message='Prepare a local test'))
    assert len(result['proposals'])==1
    assert result['proposals'][0]['status']=='pending'
    assert not copilot.jobs.tasks and copilot.store.list('job','local-operator')==[]
    assert seen[0]['model']=='openai/test-model'
    assert all(x['function']['name']!='approve' for x in seen[0]['tools'])

async def test_tutor_does_not_dispatch_unexpected_tool_calls(copilot,engagement):
    async def fake(**kwargs):
        assert all(t['function']['name'] in ('lookup_tools','get_tool_documentation','research_official_documentation') for t in kwargs.get('tools',[]))
        return {'choices':[{'message':{'content':'Explain only', 'tool_calls':[{'type':'function','id':'unexpected','function':{'name':'propose_job','arguments':proposed()['calls'][0]['arguments']}}]}}]}
    copilot.gateway=ModelGateway(completion=fake)
    result=await copilot.chat('local-operator',ChatSpec(engagement_id=engagement['id'],message='Explain only',mode='tutor'))
    assert result['proposals']==[]
    assert copilot.store.list('proposal','local-operator')==[]

async def test_ai_output_sharing_opt_in_and_redacted(copilot,engagement):
    owner='local-operator'
    job=copilot.store.put('job',owner,{'engagement_id':engagement['id'],'command':'echo observation','status':'succeeded'})
    directory=copilot.jobs.directory/job['id']; directory.mkdir()
    (directory/'combined.log').write_text('PRIVATE-OBSERVATION\nAuthorization: Bearer fake-secret-token\n')
    sent=[]
    async def fake(**kw):
        sent.append(json.dumps(kw['messages']))
        return {'choices':[{'message':{'content':'Review the result.','tool_calls':[]}}]}
    copilot.gateway=ModelGateway(completion=fake)
    await copilot.chat(owner,ChatSpec(engagement_id=engagement['id'],message='Teach me',job_id=job['id'],share_output=False))
    assert 'PRIVATE-OBSERVATION' not in sent[-1]
    await copilot.chat(owner,ChatSpec(engagement_id=engagement['id'],message='Interpret excerpt',job_id=job['id'],share_output=True))
    assert 'PRIVATE-OBSERVATION' in sent[-1] and 'fake-secret-token' not in sent[-1]

async def test_ai_provider_error_has_no_execution(copilot,engagement):
    async def fake(**kw): raise RuntimeError('provider detail and secret')
    copilot.gateway=ModelGateway(completion=fake)
    with pytest.raises(HTTPException) as e:
        await copilot.chat('local-operator',ChatSpec(engagement_id=engagement['id'],message='Hi'))
    assert e.value.status_code==502
    assert 'provider detail' not in e.value.detail
    assert not copilot.jobs.tasks

async def test_ai_routes_each_operator_and_does_not_forward_history_to_new_provider(copilot,engagement):
    pm=copilot.providers
    pm.set_key('local-operator','anthropic',AIKeyChange(api_key='personal-claude'))
    pm.save_selection('local-operator',AISelection(provider='anthropic',model='claude-test'))
    copilot.store.put('chat','local-operator',{'engagement_id':engagement['id'],'role':'user','text':'HIDDEN-OPENAI-HISTORY', 'provider':'openai'})
    seen=[]
    async def fake(**kw):
        seen.append(kw)
        return {'choices':[{'message':{'content':'Hello from Claude','tool_calls':[]}}]}
    copilot.gateway=ModelGateway(completion=fake)
    await copilot.chat('local-operator',ChatSpec(engagement_id=engagement['id'],message='Hello'))
    assert seen[0]['model']=='anthropic/claude-test' and seen[0]['api_key']=='personal-claude'
    assert 'HIDDEN-OPENAI-HISTORY' not in json.dumps(seen[0]['messages'])
    assert copilot.store.list('chat','local-operator')[0]['provider']=='anthropic'

async def test_tutor_receives_ranked_shortlist_without_requesting_lookup(copilot,engagement):
    from foxworx.registry import ToolDiscovery
    copilot.discovery=ToolDiscovery(copilot.registry,copilot.cfg.state)
    captured=[]
    async def fake(**kwargs):
        captured.append(kwargs)
        return {'choices':[{'message':{'content':'Found the local HTTP tools','tool_calls':[]}}]}
    copilot.gateway=ModelGateway(completion=fake)
    await copilot.chat('local-operator',ChatSpec(engagement_id=engagement['id'],message='Inspect HTTP headers',mode='tutor'))
    body=captured[0]['messages'][1]['content'].split('\n',1)[1]
    context=json.loads(body)
    assert context['tool_discovery']['installed_count']>0
    assert context['tool_discovery']['returned']<=10
    assert any(t['name']=='curl' for t in context['tool_discovery']['results'])
    copilot.discovery.close()

async def test_lookup_returns_counts_and_supports_pagination(copilot,engagement):
    from foxworx.registry import ToolDiscovery
    copilot.discovery=ToolDiscovery(copilot.registry,copilot.cfg.state)
    calls=[]
    async def fake(**kwargs):
        calls.append(kwargs)
        if len(calls)==1:
            return {'choices':[{'message':{'content':None,'tool_calls':[{'id':'lookup','type':'function',
                'function':{'name':'lookup_tools','arguments':json.dumps({'query':'','limit':2})}}]}}]}
        result=json.loads(kwargs['messages'][-1]['content'])
        assert result['returned']==2 and result['total_matches']>2 and result['next_cursor']
        return {'choices':[{'message':{'content':'Search is paginated','tool_calls':[]}}]}
    copilot.gateway=ModelGateway(completion=fake)
    out=await copilot.chat('local-operator',ChatSpec(engagement_id=engagement['id'],message='Find available tools',mode='tutor'))
    assert out['answer']=='Search is paginated' and not out['proposals']
    copilot.discovery.close()
