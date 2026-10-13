"""Graph must be evidence-backed, persistent, owner-scoped and not execute tools."""
from pathlib import Path
from fastapi import HTTPException
import pytest
from foxworx.operation_graph import InvestigationGraph

OWNER='local-operator'

def test_graph_reflects_rabbit_and_manual_jobs_and_history(store, cfg, engagement):
    a=store.put('rabbit', OWNER, {'engagement_id':engagement['id'],'objective':'Inspect lab services','target':'127.0.0.1','status':'running',
                                  'steps':[{'number':1,'profile':'tcp-connect','status':'failed','job_id':'a'*24},
                                           {'number':2,'profile':'http-status','status':'running','job_id':'b'*24}]})
    store.put('job',OWNER, {'id':'a'*24,'engagement_id':engagement['id'],'tool':'nmap','status':'failed','returncode':1,'started':'2026-10-01T10:00:00+00:00'})
    store.put('job',OWNER, {'id':'b'*24,'engagement_id':engagement['id'],'tool':'curl','status':'running','started':'2026-10-01T10:01:00+00:00'})
    independent=store.put('job',OWNER,{'engagement_id':engagement['id'],'tool':'dig','status':'succeeded','started':'2026-10-01T09:30:00+00:00'})
    graph=InvestigationGraph(store,cfg.state).get(OWNER,engagement['id'])
    assert len([n for n in graph['nodes'] if n['kind']=='run'])==1
    assert len([n for n in graph['nodes'] if n['kind']=='job'])==3
    assert any(x['kind']=='retry' and x['source']=='job:'+('a'*24) and x['target']=='job:'+('b'*24) for x in graph['edges'])
    assert any(n['id']=='job:'+independent['id'] and n['origin']=='manual' for n in graph['nodes'])
    assert graph['counts']['running']>=1
    assert graph['engagement_id']==engagement['id']


def test_graph_never_leaks_across_operators_or_engagements(store,cfg,engagement):
    other=store.put('engagement',OWNER,{'name':'Separate','include':['127.0.0.2'],'exclude':[]})
    store.put('job',OWNER,{'engagement_id':other['id'],'tool':'curl','status':'succeeded','command':'other-secret-command'})
    store.put('job','different-user',{'engagement_id':engagement['id'],'tool':'nmap','status':'succeeded','command':'wrong-user'})
    record=store.put('job',OWNER,{'engagement_id':engagement['id'],'tool':'dig','status':'succeeded','command':'sensitive-command'})
    graph=InvestigationGraph(store,cfg.state).get(OWNER,engagement['id'])
    assert len([n for n in graph['nodes'] if n['kind']=='job'])==1
    assert record['id'] in str(graph) and 'sensitive-command' not in str(graph)
    with pytest.raises(HTTPException) as e:
        InvestigationGraph(store,cfg.state).get('different-user',other['id'])
    assert e.value.status_code==404


def test_graph_note_persists_and_cannot_reference_other_engagement(store,cfg,engagement):
    job=store.put('job',OWNER,{'engagement_id':engagement['id'],'tool':'dig','status':'succeeded'})
    graph=InvestigationGraph(store,cfg.state)
    note=graph.annotate(OWNER,engagement['id'],'job:'+job['id'],'Lab observation, not a vulnerability')
    graph2=InvestigationGraph(store,cfg.state)
    result=graph2.get(OWNER,engagement['id'])
    assert next(n for n in result['nodes'] if n['id']=='job:'+job['id'])['note']==note['note']
    with pytest.raises(HTTPException): graph.annotate(OWNER,engagement['id'],'job:'+'a'*24,'fake')
    with pytest.raises(HTTPException): graph.annotate(OWNER,engagement['id'],'job:'+job['id'],'x'*2001)


def test_graph_parses_only_recognized_completed_tool_output(store,cfg,engagement):
    good=store.put('job',OWNER,{'engagement_id':engagement['id'],'tool':'nmap','status':'succeeded','returncode':0})
    bad=store.put('job',OWNER,{'engagement_id':engagement['id'],'tool':'nmap','status':'failed','returncode':2})
    for job in (good,bad):
        folder=cfg.state/'jobs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
        (folder/'combined.log').write_text('22/tcp open ssh\n443/tcp open https\nTOKEN=PRIVATEVALUE\n',encoding='utf8')
    graph=InvestigationGraph(store,cfg.state).get(OWNER,engagement['id'])
    obs=[n for n in graph['nodes'] if n['kind']=='observation']
    assert any(n['label']=='22/tcp open' for n in obs)
    assert len(obs)==2
    assert all('PRIVATEVALUE' not in str(n) and 'vulnerability' not in str(n) for n in obs)
    assert all(n['evidence_job_id']==good['id'] for n in obs)


def test_graph_observations_update_as_job_completes(store,cfg,engagement):
    job=store.put('job',OWNER,{'engagement_id':engagement['id'],'tool':'curl','status':'running'})
    folder=cfg.state/'jobs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    (folder/'combined.log').write_text('HTTP/1.1 200 OK\n')
    graph=InvestigationGraph(store,cfg.state)
    assert not any(n['kind']=='observation' for n in graph.get(OWNER,engagement['id'])['nodes'])
    store.put('job',OWNER,{**job,'status':'succeeded'})
    assert any(n['kind']=='observation' for n in graph.get(OWNER,engagement['id'])['nodes'])

def test_guided_jobs_group_by_approved_asset_but_not_advanced(store,cfg,engagement):
    p=store.put('proposal',OWNER,{'engagement_id':engagement['id'],'target':'http://127.0.0.1:8000/', 'scope_check':'input-checked'})
    q=store.put('proposal',OWNER,{'engagement_id':engagement['id'],'target':'http://127.0.0.1:8000/', 'scope_check':'input-checked'})
    store.put('job',OWNER,{'engagement_id':engagement['id'],'proposal_id':p['id'],'tool':'curl','status':'succeeded'})
    store.put('job',OWNER,{'engagement_id':engagement['id'],'proposal_id':q['id'],'tool':'curl','status':'succeeded'})
    manual=store.put('proposal',OWNER,{'engagement_id':engagement['id'],'target':'unapproved-hidden.test', 'scope_check':'manual-review'})
    store.put('job',OWNER,{'engagement_id':engagement['id'],'proposal_id':manual['id'],'tool':'python3','status':'succeeded'})
    graph=InvestigationGraph(store,cfg.state).get(OWNER,engagement['id'])
    assets=[n for n in graph['nodes'] if n['kind']=='asset']
    assert len(assets)==1 and assets[0]['label']=='127.0.0.1'
    assert len([e for e in graph['edges'] if e['kind']=='target-of'])==2
    assert 'unapproved-hidden.test' not in str(graph)
