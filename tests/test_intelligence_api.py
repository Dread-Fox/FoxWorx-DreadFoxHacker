"""Tool knowledge is authenticated, non-executing and operator notes require CSRF."""
import pytest
from fastapi.testclient import TestClient
from foxworx.app import create_app

@pytest.fixture
def client29(cfg,tmp_path):
    p=tmp_path/'addedtools';p.mkdir()
    f=p/'foxtesttool';f.write_text('test binary');f.chmod(0o755)
    cfg.extra_paths=(str(p),)
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as client:
        yield client,cfg

def login(c,cfg):
    origin={'Origin':cfg.origin}
    assert c.post('/api/login',json={'token':cfg.local_token},headers=origin).status_code==200
    token=c.get('/api/session').json()['csrf']
    c.headers.update({**origin,'X-Foxworx-CSRF':token})

def test_tool_knowledge_requires_authenticated_actor(client29):
    c,cfg=client29
    assert c.get('/api/tool-intelligence/foxtesttool').status_code==401
    login(c,cfg)
    result=c.get('/api/tool-intelligence/foxtesttool')
    assert result.status_code==200
    assert result.json()['name']=='foxtesttool'
    assert result.json()['execution_authorized'] is False
    assert c.get('/api/tool-intelligence/does-not-exist').status_code==404
    assert c.post('/api/tool-intelligence/foxtesttool/research',json={}).status_code==403

def test_tool_notes_persist_and_cannot_bypass_csrf(client29):
    c,cfg=client29;login(c,cfg)
    url='/api/tool-intelligence/foxtesttool/notes'
    assert c.post(url,json={'note':'Verified this tool has a help page'},headers={'X-Foxworx-CSRF':'bad'}).status_code==403
    assert c.post(url,json={'note':'Verified this tool has a help page'}).status_code==200
    result=c.get('/api/tool-intelligence/foxtesttool').json()
    assert any('Verified this tool' in x['note'] for x in result['notes'])
    assert c.post(url,json={'note':'x'}).status_code==422

def test_inventory_search_and_local_refresh(client29):
    c,cfg=client29;login(c,cfg)
    result=c.get('/api/tool-intelligence?query=foxtesttool')
    assert result.status_code==200
    assert [t['name'] for t in result.json()['tools']]==['foxtesttool']
    assert c.post('/api/tool-intelligence/foxtesttool/refresh',json={}).status_code==200
