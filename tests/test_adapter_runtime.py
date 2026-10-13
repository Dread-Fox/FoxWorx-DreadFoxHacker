"""Actual fixed HTTP adapter subprocess, on localhost only."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from shutil import which
import pytest
from fastapi.testclient import TestClient
from foxworx.app import create_app


def test_http_status_adapter_real_local_process(cfg):
    if not which('curl'):
        pytest.skip('Curl is absent on this test host')
    class Lab(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(204)
            self.send_header('X-Foxworx-Test','adapter-2.7')
            self.end_headers()
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Lab)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with TestClient(create_app(cfg,_allow_root_for_tests=True),base_url=cfg.origin,client=('127.0.0.1',50001)) as client:
            auth=client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin})
            assert auth.status_code==200
            csrf=client.get('/api/session').json()['csrf']
            client.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':csrf})
            target=f'http://127.0.0.1:{server.server_port}/'
            eng=client.post('/api/engagements',json={'name':'local-test','include':[target],'exclude':[]})
            assert eng.status_code==200,eng.text
            proposal=client.post('/api/proposals',json={'engagement_id':eng.json()['id'],
                'tool':'curl','profile':'http-status','target':target})
            assert proposal.status_code==200,proposal.text
            command=proposal.json()['command']
            assert '--output /dev/null' in command and '--max-time 20' in command
            result=client.post('/api/proposals/'+proposal.json()['id']+'/approve',json={
                'digest':proposal.json()['digest'],'authorized':True})
            assert result.status_code==200,result.text
            jid=result.json()['id']
            for _ in range(300):
                jobs=client.get('/api/jobs?engagement_id='+eng.json()['id']).json()
                job=next(j for j in jobs if j['id']==jid)
                if job['status'] not in ('running','queued','stopping'):break
                time.sleep(.01)
            assert job['status']=='succeeded',job
            output=client.get('/api/jobs/'+jid+'/output').json()['text']
            assert 'HTTP 204' in output,output
            assert 'adapter-2.7' not in output  # response body/headers discarded
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def test_schema2_registered_curl_executes_only_after_human_approval(cfg, monkeypatch):
    """Real localhost process; admin policy is injected, not installed on host."""
    if not which('curl'):
        pytest.skip('Curl is absent on this test host')
    from foxworx.adapters import AdapterPolicy
    from foxworx.command_templates import validate_template
    class Lab(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(200)
            self.send_header('X-Foxworx-Adapter', 'approved-only')
            self.end_headers()
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Lab)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    template=validate_template({'id':'curl-header-schema2','tool':'curl','label':'HTTP header metadata',
        'hint':'One approved local URL','target_kind':'url','risk':'recon','mode':'review',
        'argv':['--silent','--show-error','--head','--max-time','{param:timeout}','{target}'],
        'parameters':{'timeout':{'type':'integer','min':2,'max':8,'default':5}}})
    state={'status':'active','revision':'localhost-schema2-policy',
           'enabled_profiles':('curl-header-schema2',),
           'registered_adapters':{'curl-header-schema2':template},'max_steps':5,'max_minutes':5}
    monkeypatch.setattr(AdapterPolicy,'current',lambda self:state)
    try:
        with TestClient(create_app(cfg,_allow_root_for_tests=True),base_url=cfg.origin,client=('127.0.0.1',50002)) as client:
            assert client.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
            csrf=client.get('/api/session').json()['csrf']
            client.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':csrf})
            target=f'http://127.0.0.1:{server.server_port}/'
            eng=client.post('/api/engagements',json={'name':'schema2-local-lab','include':[target],'exclude':[]}).json()
            payload={'engagement_id':eng['id'],'profile':'curl-header-schema2','target':target,
                     'parameters':{'timeout':3},'reason':'Explicit reviewed header inspection'}
            preview=client.post('/api/registered-proposals',json=payload)
            assert preview.status_code==200,preview.text
            proposal=preview.json()
            assert proposal['adapter_id']=='curl-header-schema2'
            assert ' --max-time 3 ' in proposal['command']
            assert client.get('/api/jobs?engagement_id='+eng['id']).json()==[]
            approved=client.post('/api/proposals/'+proposal['id']+'/approve',json={
                'digest':proposal['digest'],'authorized':True})
            assert approved.status_code==200,approved.text
            jid=approved.json()['id']
            for _ in range(300):
                r=client.get('/api/jobs/'+jid+'/output').json()
                if r['job']['status'] not in ('running','queued','stopping'):break
                time.sleep(.01)
            assert r['job']['status']=='succeeded',r
            assert 'X-Foxworx-Adapter: approved-only' in r['text']
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
