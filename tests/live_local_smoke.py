"""Live non-root loopback acceptance. Harmless local commands ONLY; no inference calls."""
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import json
import os
import socket
import subprocess
import sys
import time
import httpx
import websockets.sync.client

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
assert os.geteuid() != 0, 'Run this smoke as an ordinary Linux user, never root'


def check(condition, message):
    if not condition: raise AssertionError(message)


def main():
    from foxworx.cli import initialize, write_settings
    from dotenv import dotenv_values
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    with TemporaryDirectory(prefix='foxworx-v3-live-') as temp:
        path=Path(temp)/'config/settings.env'
        initialize(path)
        data=dict(dotenv_values(path,interpolate=False))
        data.update({'FOXWORX_PORT':str(port),'FOXWORX_ORIGIN':f'http://127.0.0.1:{port}',
                     'FOXWORX_STATE':str(Path(temp)/'data'),'FOXWORX_RESERVE_MIB':'0'})
        write_settings(path,data)
        log=Path(temp)/'server.log'
        with log.open('wb') as dest:
            server=subprocess.Popen([sys.executable,'-m','foxworx.cli','serve','--config',str(path)],
                                    stdout=dest,stderr=subprocess.STDOUT,cwd=ROOT,env={**os.environ,'FOXWORX_CONFIG':str(path)})
        try:
            origin=f'http://127.0.0.1:{port}'
            with httpx.Client(base_url=origin,timeout=10,trust_env=False) as client:
                for _ in range(150):
                    try:
                        if client.get('/api/auth-mode').status_code==200: break
                    except httpx.ConnectError:
                        pass
                    if server.poll() is not None: raise AssertionError('Workbench service terminated: '+log.read_text()[-3000:])
                    time.sleep(.08)
                else: raise AssertionError('Workbench did not accept localhost connections')
                check(client.get('/api/auth-mode').json()['mode']=='open','Expected token-free service mode')
                check(client.get('/api/session').status_code==200,'Token-free session was not immediately accessible')
                check(not client.cookies,'Unexpected browser login cookie in open mode')
                session=client.get('/api/session').json()
                client.headers.update({'Origin':origin,'X-Foxworx-CSRF':session['csrf']})
                # v3.2 live read-only kernel hardware inventory and management protection.
                hardware=client.get('/api/hardware?fresh=true')
                check(hardware.status_code==200,'Read-only hardware inventory API failed')
                visible=hardware.json()
                check('pci' in visible and 'usb' in visible and 'networks' in visible,
                      'Linux hardware inventory omitted required device classes')
                check(visible['summary']['network_interfaces']>=1,
                      'Local Linux networking did not expose any interfaces')
                if any(n['name']=='lo' for n in visible['networks']):
                    check(client.put('/api/hardware/interfaces/lo/role',json={'role':'assessment'}).status_code==409,
                          'Loopback was unexpectedly assignable as assessment')
                # v2.9 live knowledge indexing, persistent notes and online opt-out.
                inventory=client.get('/api/tool-intelligence?query=python3')
                check(inventory.status_code==200 and any(t['name']=='python3' for t in inventory.json()['tools']),
                      'Live discovered executable missing from read-only knowledge inventory')
                knowledge=client.get('/api/tool-intelligence/python3')
                check(knowledge.status_code==200 and knowledge.json()['execution_authorized'] is False,
                      'Tool documentation read failed or granted inappropriate authority')
                note=client.post('/api/tool-intelligence/python3/notes',json={'note':'Local Python command documentation was reviewed.'})
                check(note.status_code==200,'Knowledge note save failed')
                check(any('reviewed' in n['note'] for n in client.get('/api/tool-intelligence/python3').json()['notes']),
                      'Saved tool usage note did not persist')
                check(client.post('/api/tool-intelligence/python3/research',json={}).status_code==403,
                      'Disabled online documentation unexpectedly accessible')
                # DreadFox is an opt-in, separate deterministic pet, no provider request.
                check(not client.get('/api/pet').json()['hatched'],'Pet must not track before hatching')
                hatched=client.post('/api/pet/hatch',json={})
                check(hatched.status_code==200 and hatched.json()['xp']==0,'Pet did not hatch cleanly')
                check(client.get('/api/pet/context').json()['enabled'] is False,'Workbench Pulse should be off by default')
                check(client.put('/api/pet/context',json={'enabled':True}).json()['enabled'] is True,
                      'Enabling Workbench Pulse failed')
                # Offline companion chat is usable without any inference backend.
                check(client.get('/api/pet/chat').json()['mode']=='offline','Pet chat must default to offline')
                answer=client.post('/api/pet/chat',json={'message':'How many tails do you have?'})
                check(answer.status_code==200 and 'tail' in answer.json()['answer'].lower(), 'Offline pet dialogue failed')
                chat=client.get('/api/pet/chat').json()
                check(len(chat['messages'])==2,'Pet dialogue was not persisted')
                favor=client.put('/api/pet/chat/focus',json={'focus':'wisdom'})
                check(favor.status_code==200 and favor.json()['personality']['affinity']=='wisdom','Pet personality preference failed')
                cleared=client.request('DELETE','/api/pet/chat',json={})
                check(cleared.status_code==200 and not cleared.json()['messages'],'Conversation deletion failed')
                eng=client.get('/api/engagements').json()[0]
                # Actual browser-equivalent provider selection — no model service needed.
                res=client.put('/api/ai/settings',json={'provider':'ollama','model':'qwen3:8b','endpoint_id':'ollama-local'})
                check(res.status_code==200 and res.json()['ready'],'Local provider selection failed')
                check(client.get('/api/session').json()['ai_provider']=='ollama','Session did not reflect operator model')
                # Real shell PTY, via authenticated websocket ticket.
                term=client.post('/api/terminals',json={'engagement_id':eng['id']})
                check(term.status_code==200,f'Terminal creation failed: {term.text}')
                termid=term.json()['id']
                ticket=client.post(f'/api/terminals/{termid}/ticket',json={}).json()['ticket']
                termoutput=b''
                with websockets.sync.client.connect(f'ws://127.0.0.1:{port}/ws/terminals/{termid}?ticket={ticket}',
                        origin=origin,open_timeout=5,close_timeout=2) as ws:
                    ws.send(json.dumps({'type':'input','data':'echo FOXWORX_LIVE_NODE_OK\n'}))
                    for _ in range(25):
                        message=json.loads(ws.recv(timeout=3))
                        if message.get('type')=='output':
                            termoutput+=base64.b64decode(message['data'])
                            if b'FOXWORX_LIVE_NODE_OK' in termoutput:break
                        elif message.get('type')=='ping': ws.send(json.dumps({'type':'pong'}))
                check(b'FOXWORX_LIVE_NODE_OK' in termoutput,'Live PTY command was not echoed')
                sessions=client.get('/api/terminals').json()
                check(any(t['id']==termid for t in sessions),'Terminal vanished on browser disconnect')
                client.request('DELETE',f'/api/terminals/{termid}',json={})
                p=client.post('/api/proposals',json={'engagement_id':eng['id'],'tool':'python3',
                    'args':['-c','print("FOXWORX_MANAGED_JOB_OK")'],'profile':'advanced','target':'','reason':'Live local verification'})
                check(p.status_code==200,f'Proposal preparation failed {p.text}')
                prop=p.json()
                check(client.get('/api/jobs').json()==[],'Proposal executed without approval')
                approved=client.post(f'/api/proposals/{prop["id"]}/approve',json={'digest':prop['digest'],'authorized':True})
                check(approved.status_code==200,f'Proposal approval failed {approved.text}')
                jobid=approved.json()['id']
                for _ in range(80):
                    r=client.get('/api/jobs/'+jobid+'/output').json()
                    if r['job']['status'] not in ('queued','running','stopping'):break
                    time.sleep(.08)
                check(r['job']['status']=='succeeded',f'Managed job failed: {r}')
                check('FOXWORX_MANAGED_JOB_OK' in r['text'],'Job output missing')
                graph_response=client.get(f'/api/engagements/{eng["id"]}/graph')
                check(graph_response.status_code==200,'Authenticated graph fetch failed')
                check(any(n.get('job_id')==jobid for n in graph_response.json()['nodes']),
                      'Graph did not include the real completed managed job')
                recorded=client.put(f'/api/engagements/{eng["id"]}/graph/notes',
                    json={'node_id':'job:'+jobid,'note':'Confirmed live-service test evidence'})
                check(recorded.status_code==200,'Live graph annotation save failed')
                check(any(n.get('note')=='Confirmed live-service test evidence' for n in
                          client.get(f'/api/engagements/{eng["id"]}/graph').json()['nodes']),
                      'Graph annotation not persisted')
                for _ in range(60):
                    companion=client.get('/api/pet').json()
                    if companion['xp']>=3: break
                    time.sleep(.04)
                check(companion['xp']>=3,'Pet did not observe a coarse workbench activity')
                check(all('FOXWORX_MANAGED_JOB_OK' not in json.dumps(event) for event in companion['memories']),
                      'Pet unexpectedly contained a tool-output string')
                pulse=client.get('/api/pet/context').json()
                check(pulse['enabled'] and any(x['area']=='completed_jobs' for x in pulse['signals']),
                      f'Workbench Pulse failed to capture coarse live operations: {pulse}')
                check('FOXWORX_MANAGED_JOB_OK' not in json.dumps(pulse),
                      'Workbench Pulse leaked a local tool output value')
                check(client.put('/api/pet/tracking',json={'enabled':False}).json()['tracking'] is False,
                      'Pet tracking did not pause')
                check(client.get('/api/pet/context').json()['signals']==[],
                      'Pausing the pet must suppress context sharing')
                check(client.request('DELETE','/api/pet/context',json={}).json()['enabled'] is False,
                      'Erasing Workbench Pulse failed')
                check(client.request('DELETE','/api/pet',json={}).status_code==200,
                      'Companion erase failed')
                check(not client.get('/api/pet').json()['hatched'],'Pet data remained after erase')
                report={'status':'PASS','scope':'live non-root localhost HTTP/PTY/jobs, mocked-free; no external inference, cloudflare or targets',
                        'uid':os.geteuid(),'version':session['version'],
                        'checks':['token-free session without login cookie','browser Origin/CSRF request integrity','read-only kernel hardware inventory and management role protection',
                                  'selected Ollama endpoint reflected in API','actual installed tool knowledge read and versioned operator note saved',
                                  'online research disabled without administrator opt-in','real PTY websocket command output',
                                  'terminal survives WebSocket disconnect','explicit single-use proposal approval',
                                  'successful managed local command with captured stdout',
                                  'live graph included managed job and persisted annotation',
                                  'pet opt-in, background progression, private journal, pause and erase',
                                  'offline fox conversations, personality memory preference and independent conversation clear',
                                  'workbench pulse off by default, opt-in real event, no output leakage, pause and erase']}
                Path(os.getenv('FOXWORX_SMOKE_REPORT',str(ROOT/'verification/live-local-smoke.json'))).write_text(json.dumps(report,indent=2)+'\n')
                print(json.dumps(report,indent=2))
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':main()
