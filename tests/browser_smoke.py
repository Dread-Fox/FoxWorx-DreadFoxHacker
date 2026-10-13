"""Offline Chromium UI smoke. Fixtures, NOT a live Cloudflare or shell E2E test.
Run: python tests/browser_smoke.py (optional playwright + system Chromium required).
No external network, managed browser policy changes, or real target traffic.
"""
from pathlib import Path
import json
import re
import sys
import os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from foxworx.jobs import PROFILES
OUT=Path(os.environ.get('FOXWORX_BROWSER_OUTPUT',str(ROOT/'verification'))); OUT.mkdir(parents=True,exist_ok=True)
catalog=json.loads((ROOT/'foxworx/catalog.json').read_text())
installed={'nmap','curl','dig','whois','openssl','jq','nuclei','httpx-toolkit','ffuf','gobuster','nikto','whatweb','sqlmap','msfconsole','tshark','tcpdump','git','tmux'}
tools=[dict(name=k,installed=k in installed,curated=True,path='/usr/bin/'+k if k in installed else '',version='fixture',**v) for k,v in catalog.items()]
fixture={'tools':tools,'profiles':PROFILES,'scanned_at':'fixture'}
script=r'''
function memoryStorage(){const values=new Map();return {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)};}
Object.defineProperty(window,'localStorage',{value:memoryStorage()});Object.defineProperty(window,'sessionStorage',{value:memoryStorage()});
window.confirm=()=>true;window.__calls=[];
const engagement={id:'aaaaaaaaaaaaaaaaaaaaaaaa',name:'Local lab · UI fixture',include:['127.0.0.1','localhost'],exclude:[],notes:'Authorized local testing. UI fixture, not a live assessment.',program_url:'',team_key:'lab-team'};
const node={version:'3.3.3',actor:'operator@example.test',csrf:'fixture-csrf',host:'kali-z790 · preview',architecture:'x86_64',python:'3.13',uid:1000,mode:'open',free_disk_bytes:18000000000,active_jobs:0,max_jobs:4,max_terminals:8,installed_executables:FIXTURE.tools.filter(t=>t.installed).length,curated_installed:18,curated_total:72,hardware:{architecture:'x86_64',profile:'workstation',device:'Linux host',distro:'kali',cpu_count:24,gpu_count:3,gpu_status:'available',ollama_installed:true,gpus:[{index:0,name:'NVIDIA GeForce RTX 3060 Ti',memory_mib:8192,free_mib:7300},{index:1,name:'NVIDIA GeForce RTX 3060 Ti',memory_mib:8192,free_mib:7100},{index:2,name:'NVIDIA GeForce RTX 3060 Ti',memory_mib:8192,free_mib:6800}],warnings:[]},ai_configured:true,ai_provider:'openai',ai_model:'gpt-fixture',state_directory:'~/.local/share/foxworx-workbench-v2',config_file:'~/.config/foxworx-workbench/settings.env',limits:{job_timeout_seconds:900,job_log_bytes:5242880},warnings:['Trusted operators share this Linux account.','GUI tools require a separate desktop.']};
let sessions=[],jobs=[],proposals=[],jobText='',rabbitRuns=[],savedToolNotes=[],teamDrafts=[],sharedChat=[],jobDeleteError=false;

const hardware={nvidia:[{index:0,name:'NVIDIA GeForce RTX 3060 Ti',memory_mib:8192,free_mib:7300,driver_version:'580'}],nvidia_status:'available',summary:{network_interfaces:3,wireless_interfaces:1,pci_devices:2,usb_devices:1,render_devices:1,accelerators:0,accelerator_candidates:1},
  networks:[{name:'lo',type:'virtual',state:'unknown',driver:'',mtu:65536,wireless_phy:'',monitor_mode:'unknown',packet_injection:'unverified',role:'management',protected:true},
            {name:'eth0',type:'ethernet-or-virtual',state:'up',driver:'e1000e',mtu:1500,wireless_phy:'',monitor_mode:'unknown',packet_injection:'unverified',role:'management',protected:true},
            {name:'wlan1',type:'wireless',state:'up',driver:'rtl88xxau',mtu:1500,wireless_phy:'phy1',monitor_mode:'supported',packet_injection:'unverified',role:'unassigned',protected:false}],
  pci:[{slot:'0000:01:00.0',category:'display',vendor_id:'0x10de',device_id:'0x2206',driver:'nvidia',class:'0x030000'},
       {slot:'0000:06:00.0',category:'processing-accelerator-candidate',vendor_id:'0x8086',device_id:'0x4321',driver:'',class:'0x120000'}],
  usb:[{port:'1-3',product:'USB WiFi',manufacturer:'Test Manufacturer',vendor_id:'0bda',product_id:'8812',speed_mbps:'480'}],
  graphics:[{node:'renderD128',device_driver:'nvidia'}],accelerators:[],accelerator_candidates:[{id:'0000:06:00.0',type:'processing-accelerator-candidate'}],
  categories:{block:{count_visible:2,names:['sda','sdb'],truncated:false},video:{count_visible:0,names:[],truncated:false}},
  warnings:['Inventory only; no hardware changes and no verified injection readiness.']};

let codexConnected=false,codexPending=false,codexTurns=[],codexInstalled=true,liteLLMInstalled=true;
let companion=null, petMode='offline', petFocus='auto', petMessages=[];
let pulseOn=false, pulseSignals=[];
function pulseState(){return {hatched:!!companion,enabled:pulseOn,tracking:!!companion?.tracking,window_days:7,signals:pulseOn&&companion?.tracking?pulseSignals:[]};}
function petChatState(){return {hatched:!!companion,mode:petMode,focus:petFocus,personality:{title:petFocus==='auto'?'Trailblazer':'Stargazer',description:'questions, discoveries and small acts of care',source:'earned from activity'},messages:petMessages};}
const snapshot=()=>companion||{hatched:false,tracking:false,name:'DreadFox',message:'Hatch to opt in'};
function newCompanion(){return {hatched:true,tracking:true,name:'DreadFox',stage:'Fox Kit',tails:1,level:1,xp:0,xp_next:20,xp_level_start:0,energy:65,bond:45,curiosity:50,mood:'Content',streak_days:0,age_days:0,today_xp:0,daily_cap:120,activity:{exploration:0,craft:0,wisdom:0,stewardship:0},next_tail:{tails:2,days:1,xp:50},next_care:{play:0,feed:0,rest:0},badges:[],memories:[{at:'2026-10-07T12:00:00+00:00',kind:'hatch',note:'A little fox spirit hatched into your workbench.',xp:0}]};}

const aiProviders=[
{id:'codex',label:'Codex · ChatGPT',cloud:true,has_key:false,requires_key:false,auth_method:'chatgpt',examples:['default'],endpoints:[],tool_support:'FOXWORX structured requests'},
{id:'openai',label:'OpenAI',cloud:true,has_key:true,requires_key:true,examples:['gpt-fixture'],endpoints:[],tool_support:'model-dependent'},
{id:'anthropic',label:'Anthropic Claude',cloud:true,has_key:false,requires_key:true,examples:['claude-test'],endpoints:[],tool_support:'model-dependent'},
{id:'ollama',label:'Ollama · local',cloud:false,has_key:false,requires_key:false,examples:['qwen3:8b'],endpoints:[{id:'ollama-local',label:'ollama-local'}],tool_support:'model-dependent'}];
const aiSettings={selected:{provider:'openai',model:'gpt-fixture',endpoint_id:''},providers:aiProviders,ready:true,engine_installed:true};
window.fetch=async(path,opts={})=>{window.__calls.push({path,method:opts.method||'GET',body:opts.body});const u=new URL(path,'http://fixture.test'),method=opts.method||'GET';let value={},status=200;const data=opts.body?JSON.parse(opts.body):{};
if(u.pathname==='/api/auth-mode')value={mode:'open'};
else if(u.pathname==='/api/session'||u.pathname==='/api/diagnostics')value=node;
else if(u.pathname==='/api/pet'&&method==='GET')value=snapshot();
else if(u.pathname==='/api/pet/hatch'&&method==='POST'){companion=newCompanion();petMode='offline';petFocus='auto';petMessages=[];pulseOn=false;pulseSignals=[];value=companion;}
else if(u.pathname==='/api/pet/name'&&method==='PUT'){companion.name=data.name;value=companion;}
else if(u.pathname==='/api/pet/tracking'&&method==='PUT'){companion.tracking=data.enabled;value=companion;}
else if(u.pathname==='/api/pet/care'&&method==='POST'){companion.bond+=2;companion.memories.unshift({at:'2026-10-07T12:00:00+00:00',kind:'care',note:'Played together beneath the stars.',xp:0});value=companion;}
else if(u.pathname==='/api/pet'&&method==='DELETE'){companion=null;petMode='offline';petFocus='auto';petMessages=[];pulseOn=false;pulseSignals=[];value={deleted:true};}
else if(u.pathname==='/api/pet/context'&&method==='GET')value=pulseState();
else if(u.pathname==='/api/pet/context'&&method==='PUT'){pulseOn=data.enabled;if(!pulseOn)pulseSignals=[];value=pulseState();}
else if(u.pathname==='/api/pet/context'&&method==='DELETE'){pulseOn=false;pulseSignals=[];value=pulseState();}
else if(u.pathname==='/api/pet/chat'&&method==='GET')value=petChatState();
else if(u.pathname==='/api/pet/chat/mode'&&method==='PUT'){petMode=data.mode;value=petChatState();}
else if(u.pathname==='/api/pet/chat/focus'&&method==='PUT'){petFocus=data.focus;value=petChatState();}
else if(u.pathname==='/api/pet/chat'&&method==='DELETE'){petMessages=[];value=petChatState();}
else if(u.pathname==='/api/pet/chat'&&method==='POST'){
  const msg=data.message,answer=petMode==='offline'?'I am a fox spirit. One tail today, many memories tomorrow.':'I am your AI-powered fox companion!';
  const provider=petMode==='ai'?aiSettings.selected.provider:'', model=petMode==='ai'?aiSettings.selected.model:'';
  petMessages.push({at:'2026-10-07',role:'user',mode:petMode,provider,model,text:msg},{at:'2026-10-07',role:'assistant',mode:petMode,provider,model,text:answer});
  value={answer,mode:petMode,provider,model,personality:petChatState().personality};
}
else if(u.pathname==='/api/ai/settings'&&(method==='GET'||method==='PUT')){
  if(method==='PUT')aiSettings.selected=data;
  aiSettings.ready=aiSettings.selected.provider==='codex'?codexConnected:aiSettings.selected.provider==='ollama'||!!aiProviders.find(p=>p.id===aiSettings.selected.provider)?.has_key;
  aiSettings.engine_installed=aiSettings.selected.provider==='codex'?codexInstalled:liteLLMInstalled;
  value=aiSettings;
}
else if(u.pathname.startsWith('/api/ai/keys/')&&method==='PUT'){aiProviders.find(p=>p.id===u.pathname.split('/').pop()).has_key=true;value={saved:true};}
else if(u.pathname.startsWith('/api/ai/keys/')&&method==='DELETE'){aiProviders.find(p=>p.id===u.pathname.split('/').pop()).has_key=false;value={cleared:true};}
else if(u.pathname==='/api/ai/models')value={models:u.searchParams.get('provider')==='codex'?['codex-fixture-model']:['qwen3:8b','llama3.1:8b']};
else if(u.pathname==='/api/ai/test')value={connected:true,provider:aiSettings.selected.provider,model:aiSettings.selected.model,reply:'OK'};
else if(u.pathname==='/api/adapter-policy')value={status:'active',revision:'test-policy',allow_installed_cli:true,max_steps:256,max_minutes:240,profiles:[
  {profile:'tcp-connect',tool:'nmap',label:'TCP inventory',hint:'One authorized host',enabled:true,installed:true,available:true},
  {profile:'http-headers',tool:'curl',label:'HTTP headers',hint:'One exact URL',enabled:true,installed:true,available:true},
  {profile:'dns-a',tool:'dig',label:'DNS A',hint:'One domain',enabled:true,installed:true,available:true},
  {profile:'tls-certificate',tool:'openssl',label:'TLS certificate',hint:'One host',enabled:true,installed:true,available:true},
  {profile:'web-fingerprint',tool:'whatweb',label:'Passive fingerprint',hint:'One URL',enabled:false,installed:false,available:false},
  {profile:'curl-metadata-tunable',tool:'curl',label:'Typed HTTP metadata',hint:'Model can choose bounded timeout',enabled:true,installed:true,available:true,mode:'autonomous',risk:'recon',parameters:{timeout:{type:'integer',min:5,max:20,default:10}}},
  {profile:'sqlmap-review',tool:'sqlmap',label:'SQLmap assessment',hint:'Intrusive manual review',enabled:true,installed:true,available:false,review_available:true,mode:'review',risk:'intrusive',parameters:{}}
]};
else if(u.pathname==='/api/registered-proposals'&&method==='POST'){
  value={id:'registered-review-001',engagement_id:engagement.id,tool:'sqlmap',profile:data.profile,source:'adapter-preview',reason:data.reason,
    command:'/usr/bin/sqlmap -u '+data.target+' --batch --level 1 --risk 1',target:data.target,
    scope_check:'admin-template-input-checked',timeout:900,status:'pending',warnings:['Fixture only; preview, not executed'],expires:Date.now()/1000+500,digest:'f'.repeat(64)};
}
else if(u.pathname==='/api/rabbit-runs'&&method==='GET')value=rabbitRuns;
else if(u.pathname==='/api/rabbit-runs'&&method==='POST'){
  if(!data.authorized){status=403;value={detail:'Authorize the run first'};}
  else {value={id:'ffffffffffffffffffffffff',status:'running',steps:[],summary:'',next_steps:'',
    provider:aiSettings.selected.provider,model:aiSettings.selected.model,...data};rabbitRuns.unshift(value);}
}
else if(u.pathname.startsWith('/api/rabbit-runs/')&&u.pathname.endsWith('/stop')){
  value={...rabbitRuns[0],status:'stopped',summary:'Operator canceled the run.',next_steps:'Review jobs.'};rabbitRuns[0]=value;
}
else if(u.pathname.startsWith('/api/rabbit-runs/')&&u.pathname.endsWith('/messages')&&method==='POST'){
  value=rabbitRuns[0];value.messages=value.messages||[];
  value.instruction_revision=(value.instruction_revision||0)+1;
  value.messages.push({message:data.message,revision:value.instruction_revision,applied_revision:null});
}
else if(u.pathname.startsWith('/api/rabbit-runs/'))value=rabbitRuns.find(r=>r.id===u.pathname.split('/').pop())||{};
else if(u.pathname==='/api/tool-intelligence'&&method==='GET'){
  const query=(u.searchParams.get('query')||'').toLowerCase();
  value={online_enabled:true,tools:FIXTURE.tools.filter(x=>x.installed && (x.name+' '+x.description).toLowerCase().includes(query)).slice(0,60)};
}
else if(u.pathname.startsWith('/api/tool-intelligence/') && method==='POST' && u.pathname.endsWith('/notes')){
  savedToolNotes.push({author:'operator@example.test',note:data.note,verified:'operator-authored'});value={saved:true};
}
else if(u.pathname.startsWith('/api/tool-intelligence/') && method==='POST' && u.pathname.endsWith('/research')){
  value={cached:false,location:'https://www.kali.org/tools/curl/',excerpt:'Official Kali reference',source:'kali'};
}
else if(u.pathname.startsWith('/api/tool-intelligence/') && method==='POST' && u.pathname.endsWith('/search')){
  value={cached:false,results:[{url:'https://www.kali.org/tools/curl/',title:'Kali curl docs',description:'Official reference'}]};
}
else if(u.pathname.startsWith('/api/tool-intelligence/') && ['GET','POST'].includes(method)){
  const name=u.pathname.split('/')[3];
  value={name,installed:true,path:'/usr/bin/'+name,package:name,version:'test-fixture',version_key:'fixture-version',category:'Web assessment',mode:'cli',cached:method==='GET',
    flags:['--head','--help'],documents:[{source:'man',location:'system man page',excerpt:'curl --head --help',trust:'untrusted-reference',expired:false}],
    notes:savedToolNotes,execution_authorized:false,caution:'Documentation never grants permissions'};
}
else if(u.pathname==='/api/discord/status')value={configured:true,channel_id:'123456789012345678',guild_id:'223456789012345678',poll_seconds:30,last_poll:1781200000,last_error:'',agent_drafts_enabled:true,automatic_agent_posting:false};
else if(u.pathname==='/api/discord/messages')value={team_key:engagement.team_key,status:{configured:true,channel_id:'123456789012345678',poll_seconds:30,last_poll:1781200000},messages:[{id:'133456789012345678',author:'Lab teammate',author_bot:false,timestamp:'2026-10-11T12:00:00Z',content:'Observed training service on port 8080 — needs verification.',url:'https://discord.com/channels/223456789012345678/123456789012345678/133456789012345678'}]};
else if(u.pathname==='/api/discord/drafts'&&method==='GET')value=teamDrafts;
else if(u.pathname==='/api/discord/drafts'&&method==='POST'){
  const draft={id:'ff1234567890123456789012',engagement_id:engagement.id,team_key:engagement.team_key,title:data.title,finding:data.finding,status:'awaiting-approval',source:'operator'};teamDrafts.push(draft);value=draft;
}
else if(u.pathname==='/api/discord/sync'&&method==='POST')value={received:0,last_poll:1781200010};
else if(u.pathname.endsWith('/review')&&u.pathname.includes('/api/discord/drafts/')&&method==='POST'){
  const draft=teamDrafts.find(x=>u.pathname.includes(x.id));draft.status=data.approved?'published':'rejected';value=draft;
}
else if(u.pathname==='/api/discord/drafts/from-rabbit'&&method==='POST'){
  const draft={id:'ff2234567890123456789012',engagement_id:engagement.id,team_key:engagement.team_key,title:'Rabbit Hole summary',finding:'Training results unverified',status:'awaiting-approval',source:'agent'};teamDrafts.push(draft);value=draft;
}
else if(u.pathname==='/api/hardware'&&method==='GET')value=hardware;
else if(u.pathname.startsWith('/api/hardware/interfaces/')&&u.pathname.endsWith('/role')&&method==='PUT'){
  const name=u.pathname.split('/')[4],nic=hardware.networks.find(n=>n.name===name);
  if(!nic||nic.protected){status=409;value={detail:'Interface protected or absent'};}
  else{nic.role=data.role;value={name,role:data.role,protected:false};}
}
else if(u.pathname==='/api/tools'||u.pathname==='/api/tools/refresh')value=FIXTURE;
else if(u.pathname.endsWith('/graph/notes')&&method==='PUT')value={node_id:data.node_id,note:data.note};
else if(u.pathname.endsWith('/graph')&&method==='GET'){
  const root={id:'engagement:'+engagement.id,kind:'engagement',label:engagement.name,status:'active',origin:'operator',created:'2026-10-07T12:00:00Z'};
  const run={id:'run:ffffffffffffffffffffffff',kind:'run',label:'Inspect local web services',status:'running',origin:'rabbit-hole',created:'2026-10-07T12:01:00Z',step_count:2};
  const first={id:'job:dddddddddddddddddddddddd',kind:'job',label:'nmap',tool:'nmap',status:'failed',origin:'rabbit-hole',created:'2026-10-07T12:02:00Z',job_id:'dddddddddddddddddddddddd'};
  const second={id:'job:eeeeeeeeeeeeeeeeeeeeeeee',kind:'job',label:'curl',tool:'curl',status:'succeeded',origin:'rabbit-hole',created:'2026-10-07T12:03:00Z',job_id:'eeeeeeeeeeeeeeeeeeeeeeee'};
  const obs={id:'observation:testfixture',kind:'observation',label:'HTTP 200 reported',status:'observed',origin:'tool-parser',created:'2026-10-07T12:04:00Z',confidence:'parsed-unverified',evidence_job_id:'eeeeeeeeeeeeeeeeeeeeeeee'};
  value={engagement_id:engagement.id,nodes:[root,run,first,second,obs],edges:[{source:root.id,target:run.id,kind:'investigation'},{source:run.id,target:first.id,kind:'run-step'},{source:run.id,target:second.id,kind:'run-step'},{source:first.id,target:second.id,kind:'retry'},{source:second.id,target:obs.id,kind:'tool-observation'}],counts:{failed:1,succeeded:1},truncated:false};
}
else if(u.pathname==='/api/engagements')value=[engagement];
else if(u.pathname==='/api/terminals'&&method==='POST'){value={id:'bbbbbbbbbbbbbbbbbbbbbbbb',engagement_id:engagement.id,status:'running'};sessions=[value];}
else if(u.pathname==='/api/terminals')value=sessions;
else if(u.pathname.endsWith('/ticket'))value={ticket:'fixture-ticket'};
else if(u.pathname.endsWith('/files'))value={files:[],limited:false};
else if(u.pathname==='/api/codex/status')value={installed:true,connected:codexConnected,busy:false,mode:codexConnected?'chatgpt':'none',plan:codexConnected?'plus':'',email:codexConnected?'operator@example.test':'',login:codexPending?{pending:true}:{},auth_method:'Codex-managed ChatGPT device login'};
else if(u.pathname==='/api/codex/login'&&method==='POST'){codexPending=true;value={verification_url:'https://auth.openai.com/codex/device',user_code:'ABCD-1234',status:'pending'};}
else if(u.pathname==='/api/codex/logout'&&method==='POST'){codexConnected=false;codexPending=false;value={connected:false};}
else if(u.pathname==='/api/codex/events')value={last_sequence:0,events:[],busy:false};
else if(u.pathname==='/api/codex/history')value=codexTurns;
else if(u.pathname==='/api/codex/turn'&&method==='POST'){
  const row={prompt:data.message,answer:'Codex test fixture: read-only code review completed.',status:'completed',model:data.model||''};codexTurns.push(row);
  value={status:'completed',answer:row.answer,thread_id:'fixture-thread',elapsed_seconds:0.04};
}
else if(u.pathname==='/api/chat'&&method==='POST'){
  value={answer:'Shared '+data.mode+' answer from '+aiSettings.selected.provider,proposals:[],provider:aiSettings.selected.provider,model:aiSettings.selected.model};
  sharedChat.push({role:'user',text:data.message},{role:'assistant',text:value.answer});
}
else if(u.pathname==='/api/chat'&&method==='DELETE'){sharedChat=[];value={cleared:true};}
else if(u.pathname==='/api/chat')value=sharedChat;
else if(u.pathname==='/api/jobs')value=jobs;
else if(u.pathname.startsWith('/api/jobs/')&&method==='DELETE'){
  const id=u.pathname.split('/').pop();
  if(jobDeleteError){status=500;value={detail:'Storage unavailable; job retained.'};}
  else{jobs=jobs.filter(j=>j.id!==id);value={deleted:true,id};}
}
else if(u.pathname==='/api/proposals'&&method==='POST'){value={...data,id:'cccccccccccccccccccccccc',argv:['/usr/bin/curl','--head',data.target],command:'/usr/bin/curl --head '+data.target,scope_check:'input-checked',warnings:['Fixture only. Input checks are not a network firewall.'],source:'operator',status:'pending',digest:'d'.repeat(64),expires:Date.now()/1000+600,timeout:900};proposals=[value];}
else if(u.pathname==='/api/proposals')value=proposals;
else if(u.pathname.endsWith('/approve')){proposals[0].status='approved';value={id:'eeeeeeeeeeeeeeeeeeeeeeee',engagement_id:engagement.id,tool:'curl',command:proposals[0].command,status:'succeeded',returncode:0,error:''};jobs=[value];jobText='HTTP/1.1 200 OK\nContent-Type: text/html\n\n[UI test fixture — not a network response]\n';}
else if(u.pathname.endsWith('/output')){
  const job=jobs.find(j=>j.id===u.pathname.split('/')[3]),offset=Number(u.searchParams.get('offset')||0);
  if(!job){status=404;value={detail:'Job not found'};}
  else value={job,text:jobText.slice(offset),offset:jobText.length};
}
else if(u.pathname==='/api/audit')value=[];
else {status=404;value={detail:'No fixture for '+path};}
return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});};
class FixtureSocket{static OPEN=1;constructor(url){this.readyState=0;setTimeout(()=>{this.readyState=1;this.onopen?.();setTimeout(()=>{this.emit({type:'ready'});this.emit({type:'output',data:btoa('\x1b[38;5;214mFOXWORX / LOCAL LAB\x1b[0m\r\nUI preview fixture - no tools were executed.\r\n\r\nfoxoperator@kali-pi4:~/engagement$ ')});},10);},10);}emit(x){this.onmessage?.({data:JSON.stringify(x)})}send(data){window.__calls.push({socket:JSON.parse(data)});}close(){this.readyState=3;this.onclose?.();}}
window.WebSocket=FixtureSocket;
'''
html=(ROOT/'static/index.html').read_text()
html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S)
html=re.sub(r'<link\b[^>]*>','',html)
css=(ROOT/'static/vendor/xterm.css').read_text()+'\n'+(ROOT/'static/app.css').read_text()
vendor=(ROOT/'static/vendor/xterm-bundle.js').read_text().replace('export{ke as default};','window.__terminalBundle=ke;')
app=(ROOT/'static/app.js').read_text().replace("import terminalBundle from './vendor/xterm-bundle.js';","const terminalBundle=window.__terminalBundle;").replace("import {createInvestigationGraph} from './graph.js';","")
app=app.replace("import {bindTerminalScroll} from './terminal-scroll.js';","")
scroll=(ROOT/'static/terminal-scroll.js').read_text().replace('export function bindTerminalScroll','function bindTerminalScroll')
graph='(function(){'+(ROOT/'static/graph.js').read_text().replace('export function createInvestigationGraph','function createInvestigationGraph')+';window.createInvestigationGraph=createInvestigationGraph;})();'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=b.new_page(viewport={'width':1600,'height':1000},device_scale_factor=1,accept_downloads=True)
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html); page.add_style_tag(content=css)
    page.add_script_tag(content='const FIXTURE='+json.dumps(fixture)+';\n'+script)
    page.add_script_tag(content=vendor)
    page.add_script_tag(content=(ROOT/'static/pet.js').read_text())
    page.add_script_tag(content=graph)
    page.add_script_tag(content=scroll)
    page.add_script_tag(content=app)
    page.set_default_timeout(7000)
    page.locator('#workbench').wait_for(state='visible'); page.wait_for_timeout(300)
    assert not errors,errors
    # Pet starts opt-in, uses its own endpoints, and never starts tool/AI work.
    assert page.locator('#pet-header-button').is_visible()
    page.click('#pet-header-button')
    assert page.locator('#pet-unhatched').is_visible()
    assert len(page.evaluate("window.__calls.filter(c=>c.path?.startsWith('/api/ai/test')||(c.path?.startsWith('/api/proposals')&&c.method==='POST'))"))==0
    page.click('#pet-hatch');page.wait_for_timeout(80)
    assert page.locator('#pet-hatched').is_visible()
    assert 'Fox Kit' in page.locator('#pet-stage').inner_text()
    assert page.locator('#fox-tails path').count()==1
    page.check('#pet-context-enable');page.wait_for_timeout(90)
    assert page.locator('#pet-context-enable').is_checked()
    page.evaluate("pulseSignals=[{area:'completed_jobs',level:'a_few'},{area:'learning_sessions',level:'some'}]")
    page.click('#pet-refresh');page.wait_for_timeout(110)
    assert 'Completed jobs' in page.locator('#pet-context-preview').inner_text()
    page.locator('.pet-pulse').screenshot(path=str(OUT/'ui-pet-workbench-pulse.png'))
    assert not page.locator('#pet-context-clear').is_disabled()
    page.click('#pet-context-clear');page.wait_for_timeout(80)
    assert not page.locator('#pet-context-enable').is_checked()
    assert 'No operations data' in page.locator('#pet-context-preview').inner_text()
    page.click('#pet-play');page.wait_for_timeout(80)
    assert 'Played together' in page.locator('#pet-memories').inner_text()
    # Offline conversation and chosen memory theme require no model calls.
    page.fill('#pet-chat-input','Hello, what do you remember?')
    page.click('#pet-chat-send');page.wait_for_timeout(80)
    assert 'fox spirit' in page.locator('#pet-chat-messages').inner_text()
    assert len(page.evaluate("window.__calls.filter(c=>c.path==='/api/ai/test')"))==0
    page.select_option('#pet-chat-focus','wisdom');page.wait_for_timeout(60)
    assert 'Stargazer' in page.locator('#pet-chat-personality').inner_text()
    page.check('#pet-chat-ai');page.wait_for_timeout(80)
    assert 'Selected AI' in page.locator('#pet-chat-mode-label').inner_text()
    page.fill('#pet-chat-input','Hi again!')
    page.click('#pet-chat-send');page.wait_for_timeout(80)
    assert 'AI-powered fox' in page.locator('#pet-chat-messages').inner_text()
    assert page.locator('#pet-chat-input').input_value()==''
    page.screenshot(path=str(OUT/'ui-pet-conversations.png'),full_page=True)
    page.click('#pet-chat-clear');page.wait_for_timeout(70)
    assert 'Say hello' in page.locator('#pet-chat-messages').inner_text()
    page.uncheck('#pet-chat-ai');page.wait_for_timeout(60)
    assert 'Offline' in page.locator('#pet-chat-mode-label').inner_text()
    page.screenshot(path=str(OUT/'ui-pet-desktop.png'),full_page=True)
    # Longevity illustration fixture: not real earned progress.
    page.evaluate('''() => {companion.tails=9; companion.stage='Nine-Tailed Guardian'; companion.name='DreadFox'; companion.level=14; companion.xp=3900; companion.xp_level_start=3380; companion.xp_next=3920; companion.age_days=402; companion.bond=95; companion.curiosity=95; companion.mood='Delighted'; companion.next_tail=null; }''')
    page.evaluate('''async () => { const r = await fetch('/api/pet'); window.__previewPet = await r.json(); }''')
    page.click('#pet-refresh');page.wait_for_timeout(100)
    assert page.locator('#fox-tails path').count()==9
    page.screenshot(path=str(OUT/'ui-pet-nine-tails-fixture.png'),full_page=True)
    page.evaluate('''() => {companion=newCompanion();}''')
    page.click('#pet-refresh');page.wait_for_timeout(60)
    page.locator('.pet-settings summary').click()
    page.fill('#pet-rename','Kitsune Prime');page.click('#pet-rename-save');page.wait_for_timeout(60)
    assert 'Kitsune Prime' in page.locator('#pet-name').inner_text()
    page.uncheck('#pet-tracking');page.wait_for_timeout(60)
    assert not page.locator('#pet-tracking').is_checked()
    page.click('#tab-terminal')
    page.click('#first-terminal'); page.wait_for_timeout(250)
    assert 'Connected' in page.locator('#terminal-state').inner_text()
    assert page.locator('.xterm-screen').is_visible()
    assert page.locator('#terminal-scroll-controls').is_visible()
    page.evaluate("new Promise(resolve=>S.term.write(Array.from({length:150},(_,i)=>`history ${i}\\r\\n`).join(''),resolve))")
    page.wait_for_function("!document.getElementById('terminal-scroll').disabled")
    page.evaluate("const slider=document.getElementById('terminal-scroll');slider.value='20';slider.dispatchEvent(new Event('input'))")
    page.wait_for_function('S.term.buffer.active.viewportY===20')
    page.locator('#terminal-latest').click()
    page.wait_for_function('S.term.buffer.active.viewportY===S.term.buffer.active.baseY')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Desktop has horizontal overflow'
    page.screenshot(path=str(OUT/'ui-desktop-dark.png'),full_page=True)
    page.click('#tab-node');page.wait_for_timeout(100)
    assert '3 NVIDIA' in page.locator('#node-cards').inner_text()
    assert page.locator('#node-details').inner_text().count('RTX 3060 Ti')==3
    page.screenshot(path=str(OUT/'ui-node-workstation.png'),full_page=True)
    # v3.3 simulated hardware inventory / role binding / no management rewrites.
    page.click('#tab-hardware');page.wait_for_timeout(70)
    assert 'Network adapters' in page.locator('#view-hardware').inner_text()
    assert 'eth0' in page.locator('#hardware-network').inner_text()
    assert 'wlan1' in page.locator('#hardware-network').inner_text()
    assert page.locator('#hardware-network select').first.is_disabled()
    page.locator('#hardware-network .hardware-device').last.locator('select').select_option('assessment')
    page.locator('#hardware-network .hardware-device').last.get_by_role('button',name='Save role').click()
    page.wait_for_timeout(80)
    assert 'role: assessment' in page.locator('#hardware-network').inner_text()
    assert 'PCI' in page.locator('#hardware-buses').inner_text()
    page.screenshot(path=str(OUT/'ui-hardware-desktop.png'),full_page=True)
    # v3.3 engagement-matched Discord team channel with review-only drafts.
    page.click('#tab-team');page.wait_for_timeout(110)
    assert 'Lab teammate' in page.locator('#team-messages').inner_text()
    assert 'lab-team' in page.locator('#team-key-label').inner_text()
    page.screenshot(path=str(OUT/'ui-discord-team-desktop.png'),full_page=True)
    page.fill('#team-draft-title','Lab HTTP observation')
    page.fill('#team-draft-content','Port 8080 observed on authorized test host; not yet confirmed.')
    page.click('#team-draft-save');page.wait_for_timeout(100)
    assert 'awaiting-approval' in page.locator('#team-drafts').inner_text()
    assert not page.evaluate("window.__calls.some(x=>x.path?.endsWith('/review'))"), 'No Discord post should happen from draft action'
    page.locator('#team-drafts .team-review .primary').first.click();page.wait_for_timeout(90)
    assert 'published' in page.locator('#team-drafts').inner_text()
    page.click('#tab-intelligence')
    page.fill('#intel-search','curl');page.click('#intel-find')
    page.locator('#intel-results button').first.click()
    assert page.locator('#intel-toolname').inner_text()=='curl'
    page.wait_for_function("document.querySelector('#intel-flags').textContent.includes('--head')")
    assert 'man' in page.locator('#intel-docs').inner_text()
    page.fill('#intel-note','Manual confirms --head on this installed version.')
    page.click('#intel-save-note');page.wait_for_timeout(40)
    assert 'Manual confirms' in page.locator('#intel-notes').inner_text()
    page.click('#intel-online');page.wait_for_timeout(40)
    page.click('#intel-search-web');page.wait_for_timeout(40)
    assert 'Kali curl docs' in page.locator('#intel-docs').inner_text()
    page.locator('#view-intelligence').evaluate('(el)=>el.scrollTop=0')
    page.screenshot(path=str(OUT/'ui-tool-intelligence-desktop.png'),full_page=True)
    print('BROWSER: graph desktop', flush=True)
    # v3 graph: execution branches, alternate tool, observed evidence and annotation.
    page.click('#tab-graph');page.wait_for_timeout(130)
    assert page.locator('.fox-graph-node').count()>=4
    assert '2 jobs' in page.locator('#graph-total').inner_text()
    assert page.locator('path[stroke="#ef9b67"]').count()>=1, 'Retry edge missing'
    page.locator('.fox-graph-node').filter(has=page.locator('text',has_text='nmap')).first.click()
    assert page.locator('#graph-inspector').get_by_text('nmap').count()>=1
    page.fill('#graph-note-text','Lab scan reviewed; inspect before reporting')
    page.get_by_role('button',name='Save annotation').click();page.wait_for_timeout(70)
    assert len(page.evaluate("window.__calls.filter(c=>c.path?.endsWith('/graph/notes'))"))>=1
    page.select_option('#graph-mode','investigation');page.wait_for_timeout(60)
    assert page.locator('.fox-graph-node').count()>=4
    assert 'HTTP 200' in page.locator('#graph-node-list').inner_text()
    page.locator('#view-graph').evaluate('(e)=>e.scrollTop=0')
    page.screenshot(path=str(OUT/'ui-investigation-graph-desktop.png'),full_page=True)
    page.fill('#graph-filter','curl');page.wait_for_timeout(35)
    assert 'curl' in page.locator('#graph-node-list').inner_text()
    page.fill('#graph-filter','')
    with page.expect_download(timeout=7000) as dl:page.click('#graph-export-json')
    dl.value.save_as(str(OUT/'graph-fixture-export.json'))
    assert len(json.loads((OUT/'graph-fixture-export.json').read_text())['nodes'])>=4
    with page.expect_download(timeout=7000) as dl:page.click('#graph-export-svg')
    dl.value.save_as(str(OUT/'graph-fixture-export.svg'))
    assert '<svg' in (OUT/'graph-fixture-export.svg').read_text()
    with page.expect_download(timeout=7000) as dl:page.click('#graph-export-png')
    dl.value.save_as(str(OUT/'graph-fixture-export.png'))
    assert (OUT/'graph-fixture-export.png').read_bytes().startswith(b'\x89PNG')
    page.click('#graph-zoom-in');assert page.locator('#graph-zoom-label').inner_text()!='82%'
    page.click('#tab-terminal')
    page.click('#ai-settings-open');page.locator('#ai-settings-dialog').wait_for(state='visible')
    page.select_option('#ai-provider','anthropic')
    page.fill('#ai-key','sk-only-a-fixture')
    page.click('#ai-save-key');page.wait_for_timeout(50)
    assert page.locator('#ai-provider').input_value()=='anthropic','Key save should preserve draft provider'
    assert page.locator('#ai-key').input_value()==''
    page.fill('#ai-model','claude-test');page.click('#ai-save-selection');page.wait_for_timeout(50)
    assert 'Anthropic' in page.locator('#ai-selection-label').inner_text()
    page.select_option('#ai-provider','ollama');page.fill('#ai-model','qwen3:8b')
    page.click('#ai-save-selection');page.wait_for_timeout(50)
    assert 'Ollama' in page.locator('#ai-selection-label').inner_text()
    page.click('#ai-discover');page.wait_for_timeout(50)
    assert '2 models' in page.locator('#ai-settings-result').inner_text()
    page.click('#ai-test-connection');page.wait_for_timeout(50)
    assert 'Connected to ollama' in page.locator('#ai-settings-result').inner_text()
    page.screenshot(path=str(OUT/'ui-model-selector.png'),full_page=True)
    page.locator('#ai-settings-dialog [data-close]').first.click()

    # Rabbit Hole requires a single visible grant and never calls per-job approval UI.
    page.select_option('#ai-mode','rabbit')
    assert page.locator('#rabbit-config').is_visible()
    assert not page.locator('#chat-context').is_visible()
    page.locator('input[name=\"rabbit-profile\"][value=\"sqlmap-review\"]').wait_for(state='attached')
    page.fill('#rabbit-adapter-search','sqlmap')
    assert page.locator('.rabbit-adapter-row:not([hidden])').count()==1
    assert page.locator('input[name=rabbit-profile][value=sqlmap-review]').is_disabled()
    page.fill('#rabbit-target','http://127.0.0.1/')
    page.locator('.rabbit-adapter-row:not([hidden]) button').click()
    page.locator('#approval-dialog').wait_for(state='visible')
    assert '/usr/bin/sqlmap' in page.locator('#approval-command').inner_text()
    assert len(page.evaluate("window.__calls.filter(c=>c.path?.endsWith('/approve'))"))==0
    page.evaluate("document.getElementById('approval-dialog').close()")
    page.fill('#rabbit-adapter-search','')
    assert page.locator('.rabbit-adapter-row:not([hidden])').count()>=5
    page.screenshot(path=str(OUT/'ui-cli-adapters-desktop.png'),full_page=True)
    page.fill('#chat-input','Inspect the local lab TCP services safely')
    page.fill('#rabbit-target','127.0.0.1')
    page.fill('#rabbit-steps','4')
    page.click('#send-chat');page.wait_for_timeout(65)
    assert page.locator('#chat-input').input_value().startswith('Inspect'), 'Unapproved request must preserve draft'
    assert len(page.evaluate("window.__calls.filter(c=>c.path==='/api/rabbit-runs' && c.method==='POST')"))==0
    page.check('#rabbit-authorized')
    page.click('#send-chat');page.wait_for_timeout(90)
    assert page.locator('#rabbit-progress').is_visible()
    assert 'running' in page.locator('#rabbit-run-status').inner_text()
    assert len(page.evaluate("window.__calls.filter(c=>c.path==='/api/rabbit-runs' && c.method==='POST')"))==1
    assert len(page.evaluate("window.__calls.filter(c=>c.path?.endsWith('/approve'))"))==0
    page.screenshot(path=str(OUT/'ui-rabbit-desktop.png'),full_page=True)
    page.click('#rabbit-stop');page.wait_for_timeout(80)
    assert 'stopped' in page.locator('#rabbit-run-status').inner_text()
    page.select_option('#rabbit-execution-mode','installed_cli')
    assert page.locator('#rabbit-steps').input_value()=='64'
    assert page.locator('#rabbit-minutes').input_value()=='60'
    page.fill('#chat-input','Discover and inspect the local service')
    page.check('#rabbit-authorized');page.click('#send-chat');page.wait_for_timeout(90)
    assert page.locator('#send-chat').inner_text()=='Send instruction'
    page.fill('#chat-input','Try another installed tool')
    page.click('#send-chat');page.wait_for_timeout(90)
    followups=page.evaluate("window.__calls.filter(c=>c.path?.endsWith('/messages'))")
    assert json.loads(followups[-1]['body'])['message']=='Try another installed tool'
    assert 'Received' in page.locator('#rabbit-instructions').inner_text()
    page.screenshot(path=str(OUT/'ui-autonomous-cli-desktop.png'),full_page=True)
    starts=page.evaluate("window.__calls.filter(c=>c.path==='/api/rabbit-runs' && c.method==='POST')")
    assert json.loads(starts[-1]['body'])['execution_mode']=='installed_cli' and json.loads(starts[-1]['body'])['profiles']==[]
    page.click('#rabbit-stop');page.wait_for_timeout(80)
    page.select_option('#rabbit-execution-mode','workflows')
    page.select_option('#ai-mode','copilot')
    assert not page.locator('#rabbit-config').is_visible()
    assert page.locator('#chat-context').is_visible()
    page.click('#ai-settings-open')
    page.select_option('#ai-provider','codex')
    page.locator('#codex-config').wait_for(state='visible')
    assert page.locator('#codex-signin').is_visible()
    assert not page.locator('#ai-key-section').is_visible()
    assert not page.locator('#ai-endpoint').is_visible()
    page.fill('#ai-model','codex-fixture-model')
    page.evaluate('liteLLMInstalled=false')
    page.click('#ai-save-selection');page.wait_for_timeout(60)
    assert page.locator('#ai-mode').input_value()=='copilot'
    assert not page.evaluate('S.session.ai_configured')
    page.click('#codex-signin')
    page.locator('#codex-device').wait_for(state='visible')
    assert 'ABCD-1234' in page.locator('#codex-user-code').inner_text()
    assert 'auth.openai.com' in page.locator('#codex-verify-url').get_attribute('href')
    page.evaluate('codexConnected=true;codexPending=false')
    page.click('#codex-refresh');page.wait_for_timeout(50)
    assert 'connected' in page.locator('#codex-badge').inner_text().lower()
    assert page.evaluate('S.session.ai_configured'), 'Codex should work without LiteLLM'
    page.click('#ai-discover');page.wait_for_timeout(50)
    assert page.locator('#ai-model-options option').first.get_attribute('value')=='codex-fixture-model'
    page.screenshot(path=str(OUT/'ui-codex-desktop.png'),full_page=True)
    page.locator('#ai-settings-dialog [data-close]').first.click()
    for mode in ('tutor','copilot'):
        page.select_option('#ai-mode',mode)
        assert 'Codex' in page.locator('#ai-selection-label').inner_text()
        assert page.locator('#chat-context').is_visible()
        page.fill('#chat-input','Help with this lab finding')
        page.click('#send-chat');page.wait_for_timeout(90)
        assert 'Shared '+mode+' answer from codex' in page.locator('#chat-messages').inner_text()
        assert page.evaluate("JSON.parse(window.__calls.filter(c=>c.path==='/api/chat'&&c.method==='POST').at(-1).body).mode")==mode
    assert not page.evaluate("window.__calls.some(c=>c.path==='/api/codex/turn'&&c.method==='POST')")
    page.select_option('#ai-mode','rabbit');page.wait_for_timeout(50)
    assert 'Codex' in page.locator('#ai-selection-label').inner_text()
    page.fill('#chat-input','Check only the authorized lab')
    page.check('#rabbit-authorized');page.click('#send-chat');page.wait_for_timeout(80)
    assert 'codex/codex-fixture-model' in page.locator('#rabbit-run-budget').inner_text()
    page.click('#rabbit-stop');page.wait_for_timeout(50)
    page.select_option('#ai-mode','copilot')
    page.click('#clear-chat');page.wait_for_timeout(50)
    assert 'Shared' not in page.locator('#chat-messages').inner_text()
    page.click('#ai-settings-open');page.wait_for_timeout(60)
    page.click('#codex-signout');page.wait_for_timeout(80)
    assert page.locator('#codex-signin').is_visible()
    assert not page.evaluate('S.session.ai_configured')
    page.evaluate('liteLLMInstalled=true')
    page.select_option('#ai-provider','ollama');page.fill('#ai-model','qwen3:8b')
    page.click('#ai-save-selection');page.wait_for_timeout(50)
    page.locator('#ai-settings-dialog [data-close]').first.click()

    page.fill('#tool-search','curl');page.locator('#tool-list button').first.click()
    assert page.locator('#target-field').is_visible()
    page.fill('#tool-target','http://127.0.0.1:8080')
    page.click('#tool-prepare');page.locator('#approval-dialog').wait_for(state='visible')
    assert page.locator('#approve-run').is_disabled()
    assert len(page.evaluate("window.__calls.filter(c=>c.path?.endsWith('/approve'))"))==0
    page.screenshot(path=str(OUT/'ui-approval.png'),full_page=True)
    page.check('#approval-check');page.click('#approve-run');page.wait_for_timeout(200)
    assert '200 OK' in page.locator('#job-output').inner_text()
    assert len(page.evaluate("window.__calls.filter(c=>c.path?.endsWith('/approve'))"))==1
    page.click('#job-to-ai');assert not page.locator('#share-output').is_checked()
    page.click('#theme-toggle');page.screenshot(path=str(OUT/'ui-desktop-light.png'),full_page=True)
    assert page.locator('#login-screen').is_hidden() and page.locator('#logout-button').is_hidden(), 'Token-free UI must not prompt for login or offer sign out'
    assert page.locator('#delete-selected').is_visible() and page.locator('#delete-selected').is_enabled()
    page.evaluate('window.confirm=()=>false')
    page.click('#delete-selected');page.wait_for_timeout(40)
    assert not page.evaluate("window.__calls.some(c=>c.path?.startsWith('/api/jobs/')&&c.method==='DELETE')")
    page.evaluate('window.confirm=()=>true;jobDeleteError=true')
    page.click('#delete-selected');page.wait_for_timeout(80)
    assert page.locator('#job-list .job-row').count()==1
    assert '200 OK' in page.locator('#job-output').inner_text()
    assert page.locator('#delete-selected').is_enabled()
    page.evaluate('jobDeleteError=false;jobs[0].status="running"')
    page.click('#refresh-jobs');page.wait_for_timeout(70)
    assert page.locator('#delete-selected').is_disabled()
    assert page.locator('#stop-selected').is_enabled()
    page.evaluate('jobs[0].status="succeeded"')
    page.click('#refresh-jobs');page.wait_for_timeout(70)
    page.check('#share-output')
    page.click('#delete-selected');page.wait_for_timeout(100)
    assert page.locator('#job-list .job-row').count()==0
    assert 'Select a job' in page.locator('#output-label').inner_text()
    assert page.locator('#delete-selected').is_disabled() and page.locator('#stop-selected').is_disabled()
    assert page.locator('#ai-job').input_value()=='' and not page.locator('#share-output').is_checked()
    assert page.locator('#job-count').inner_text()=='0'
    page.evaluate("jobs=[{id:'cccccccccccccccccccccccc',tool:'curl',status:'failed',returncode:1,error:''}]")
    page.click('#refresh-jobs');page.wait_for_timeout(60)
    page.locator('#job-list .job-row button').first.click();page.wait_for_timeout(50)
    assert page.locator('#delete-selected').is_enabled(), 'Failed jobs must also be deletable'
    page.evaluate('jobs=[]')
    page.click('#refresh-jobs');page.wait_for_timeout(70)
    assert page.evaluate("S.selectedJob===''") and page.locator('#delete-selected').is_disabled()
    page.click('#tab-terminal');page.click('#theme-toggle')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
    controls=page.locator('#terminal-scroll-controls').bounding_box()
    view=page.locator('#view-terminal').bounding_box()
    assert controls['y']+controls['height']<=view['y']+view['height'], 'Mobile history controls are clipped'
    screen=page.locator('.xterm-screen').bounding_box()
    wrap=page.locator('#terminal-wrap').bounding_box()
    assert screen['height']<=wrap['height'], 'Terminal rows extend below the visible pane after resizing'
    assert 'history 149' in page.locator('.xterm-rows').inner_text(), 'Newest output is not rendered after mobile resizing'
    assert page.locator('#copy-selection').bounding_box()['height']>=44
    page.screenshot(path=str(OUT/'ui-mobile.png'),full_page=True)
    page.click('#tab-jobs')
    assert page.locator('#delete-selected').is_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile Jobs controls overflow'
    page.screenshot(path=str(OUT/'ui-job-deletion-mobile.png'),full_page=True)
    print('BROWSER: graph mobile', flush=True)
    page.click('#tab-graph');page.wait_for_timeout(100)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile graph overflow'
    page.screenshot(path=str(OUT/'ui-investigation-graph-mobile.png'),full_page=True)
    page.click('#tab-team');page.wait_for_timeout(90)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile Discord team view overflows'
    page.screenshot(path=str(OUT/'ui-discord-team-mobile.png'),full_page=True)
    page.click('#tab-hardware');page.wait_for_timeout(70)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile hardware inventory overflows'
    page.screenshot(path=str(OUT/'ui-hardware-mobile.png'),full_page=True)
    page.click('#tab-intelligence');page.wait_for_timeout(70)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile tool intelligence overflows'
    page.screenshot(path=str(OUT/'ui-tool-intelligence-mobile.png'),full_page=True)
    page.click('#tab-terminal')
    page.select_option('#ai-mode','rabbit')
    assert page.locator('#rabbit-config').is_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile Rabbit Hole has horizontal overflow'
    page.screenshot(path=str(OUT/'ui-rabbit-mobile.png'),full_page=True)
    page.select_option('#rabbit-execution-mode','installed_cli')
    page.fill('#rabbit-target','127.0.0.1')
    page.fill('#chat-input','Inspect the authorized local service')
    page.check('#rabbit-authorized');page.click('#send-chat');page.wait_for_timeout(90)
    page.fill('#chat-input','Try an alternative HTTP tool')
    page.click('#send-chat');page.wait_for_timeout(90)
    assert 'Received' in page.locator('#rabbit-instructions').inner_text()
    assert page.locator('#send-chat').is_enabled()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=str(OUT/'ui-autonomous-cli-mobile.png'),full_page=True)
    page.click('#rabbit-stop');page.wait_for_timeout(80)
    page.select_option('#ai-mode','copilot')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile has horizontal overflow'
    page.click('#ai-settings-open');page.wait_for_timeout(50)
    page.select_option('#ai-provider','codex')
    assert page.locator('#codex-config').is_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile Codex panel overflow'
    page.screenshot(path=str(OUT/'ui-codex-mobile.png'),full_page=True)
    page.select_option('#ai-provider','ollama')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile model settings have horizontal overflow'
    page.screenshot(path=str(OUT/'ui-mobile-model-selector.png'),full_page=True)
    page.locator('#ai-settings-dialog [data-close]').first.click()
    page.click('#tab-pet');page.wait_for_timeout(80)
    page.locator('#view-pet').evaluate('(e)=>e.scrollTop=0')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile companion has horizontal overflow'
    assert page.locator('#pet-hatched').is_visible()
    page.evaluate("document.querySelector('#toast').hidden=true")
    page.screenshot(path=str(OUT/'ui-pet-mobile.png'),full_page=True)
    page.locator('#pet-chat').screenshot(path=str(OUT/'ui-pet-chat-mobile.png'))
    page.check('#pet-context-enable');page.wait_for_timeout(70)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile Pulse has horizontal overflow'
    page.locator('.pet-pulse').screenshot(path=str(OUT/'ui-pet-pulse-mobile.png'))
    page.uncheck('#pet-context-enable');page.wait_for_timeout(75)
    page.click('#tab-terminal')
    page.click('#toggle-tools');assert page.locator('.toolbox').is_visible()
    page.select_option('#availability-filter','curated');page.fill('#tool-search','burpsuite')
    page.locator('#tool-list button').first.click()
    assert not page.locator('#tool-prepare').is_visible(), 'GUI tool must not masquerade as a foreground job'
    assert not errors,errors
    result={'mode':'Offline UI fixture smoke; NOT live browser-to-backend E2E','browser':b.version,'page_errors':errors,
        'checks':['actual HTML/CSS/JS initialize','vendored xterm renders','no horizontal overflow at 1600px and 390px',
                  'guided preview before approval','approval initially disabled','single explicit approval request',
                  'job output display','finished/failed job deletion, confirmation cancellation, storage error recovery, deleted-job context reset, external deletion and mobile controls','AI output-sharing remains opt-in','light/dark themes','mobile toolbox','GUI tool has no misleading job launcher','per-operator cloud key and local model selection','local model discovery','connection test','AI settings preserve draft on key save','x86-64 multi-GPU node diagnostics (fixture)','pet opt-in hatch, care, rename and pause','pet isolated from tool approvals','offline companion chat','AI pet conversation opt-in','pet chat erasure and personality focus','pet responsive mobile/desktop','Workbench Pulse opt-in, preview, immediate deletion and narrow-screen controls','Rabbit Hole one-time authorization, installed-CLI selection, active-run supplemental instructions, no per-job approval request, visible cancellation and responsive layout','v2.8 registered auto/review adapters, searchable catalog, review-only command preview','v2.9 installed-tool intelligence docs and versioned notes; desktop/mobile layout and offline search fixture','v3.0 execution/investigation graph, retry links, inspector, annotations, zoom, filters and mobile layout','unified Codex provider, independent Tutor/Copilot/Rabbit modes, ChatGPT sign-in, shared chat/clear, model discovery, operation without LiteLLM, desktop/mobile UI','v3.2 read-only hardware inventory, protected network roles, mobile inventory and device selection','v3.3 Discord team findings, draft review, agent context and responsive team UI'],
        'status':'PASS','screenshots':'ui-*.png; all values and terminal output are fixtures'}
    (OUT/'browser-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));b.close()
