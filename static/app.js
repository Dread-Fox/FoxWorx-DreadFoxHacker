import terminalBundle from './vendor/xterm-bundle.js';
import {createInvestigationGraph} from './graph.js';
import {bindTerminalScroll} from './terminal-scroll.js';
const {Terminal, FitAddon} = terminalBundle;
const $ = id => document.getElementById(id);
const S = {session:null, csrf:'', engagements:[], eng:'', tools:[], profiles:{}, tool:null,
  proposal:null, jobs:[], selectedJob:'', deletingJob:'', outputOffset:0, outputText:'', term:null, fit:null,
  terminalId:'', ws:null, reconnectTimer:null, reconnectTries:0, view:'terminal', limit:80,
  graph:null, polling:false, editingEngagement:'', chatBusy:false, toastTimer:null, rabbitRun:null, rabbitTimer:null, rabbitPolicy:null,
  codex:{installed:false,connected:false,busy:false}, hardware:null, teamLoading:false};
const active = status => ['queued','running','stopping'].includes(status);
const finishedJob = status => ['succeeded','failed','stopped','timed_out','output_limit','interrupted'].includes(status);
const bytes = n => n >= 1073741824 ? (n/1073741824).toFixed(1)+' GiB' : n >= 1048576 ? (n/1048576).toFixed(1)+' MiB' : n >= 1024 ? (n/1024).toFixed(1)+' KiB' : n+' B';
const text = (tag, value, cls='') => {const x=document.createElement(tag);x.textContent=value;if(cls)x.className=cls;return x;};
const option = (value,label) => {const x=text('option',label);x.value=value;return x;};
const prettyStatus = s => s.replaceAll('_',' ');
const shellQuote = s => /^[a-zA-Z0-9_./:+-]+$/.test(s) ? s : "'"+s.replaceAll("'","'\\''")+"'";
function toast(message){$('toast').textContent=message;$('toast').hidden=false;$('announcer').textContent=message;clearTimeout(S.toastTimer);S.toastTimer=setTimeout(()=>$('toast').hidden=true,7000);}
function explainError(data){if(Array.isArray(data?.detail))return data.detail.map(x=>`${x.loc?.slice(1).join('.') || 'Input'}: ${x.msg}`).join('\n');return data?.detail || 'The request could not be completed.';}
async function api(path, method='GET', body=undefined, customHeaders={}){
  const headers={...customHeaders};
  if(method!=='GET')headers['X-Foxworx-CSRF']=S.csrf;
  let payload=body;
  if(body!==undefined && !(body instanceof Blob)){headers['Content-Type']='application/json';payload=JSON.stringify(body);}
  const ctrl=new AbortController(), timer=setTimeout(()=>ctrl.abort(),path==='/api/codex/turn'?190000:(path==='/api/chat'||path==='/api/ai/test'||(path==='/api/pet/chat'&&method==='POST')?95000:70000));
  try{
    const r=await fetch(path,{method,headers,body:payload,credentials:'same-origin',cache:'no-store',signal:ctrl.signal});
    if(!r.headers.get('content-type')?.includes('application/json'))throw new Error('Session or gateway returned an unexpected page. Reload and sign in again.');
    const data=await r.json();
    if(!r.ok){const error=new Error(explainError(data));error.status=r.status;throw error;}
    return data;
  }catch(e){if(e.name==='AbortError')throw new Error('The response timed out. Check Jobs before repeating an action; the server may have received it.');throw e;}
  finally{clearTimeout(timer);}
}
function handle(fn){return async event=>{try{await fn(event);}catch(e){toast(e.message);}};}
async function copy(value){if(!value)return toast('Nothing selected to copy.');try{await navigator.clipboard.writeText(value);toast('Copied to clipboard.');}catch{toast('Clipboard access was blocked. Select the text and copy it manually.');}}
function openDialog(id){const d=$(id);if(!d.open)d.showModal();}
function currentEng(){return S.engagements.find(x=>x.id===S.eng);}
function setTheme(theme){document.documentElement.dataset.theme=theme;localStorage.setItem('foxworx-theme',theme);}
setTheme(localStorage.getItem('foxworx-theme') || 'dark');
$('theme-toggle').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('help-button').onclick=()=>openDialog('help-dialog');
$('toggle-tools').onclick=()=>document.body.classList.toggle('tools-open');
$('logout-button').onclick=handle(async()=>{const r=await api('/api/logout','POST',{});disconnectTerminal();location.href=r.cloudflare_logout || '/';});

async function boot(){
  try{
    const mode=await api('/api/auth-mode');
    $('logout-button').hidden=(mode.mode==='open');
    // External traffic should use HTTPS. The loopback listener itself stays HTTP.
    // Do not trust forwarded headers: only redirect to the approved host.
    if(mode.mode!=='open' && mode.public_origin && location.protocol==='http:' &&
       location.host===new URL(mode.public_origin).host){
      location.replace(mode.public_origin + location.pathname + location.search + location.hash);
      return;
    }
    try{S.session=await api('/api/session');}catch(e){
      if(e.status===401 && ['local','proxy'].includes(mode.mode)){$('login-form').hidden=false;$('login-loading').hidden=true;$('setup-token').focus();return;}
      throw e;
    }
    S.csrf=S.session.csrf;$('login-screen').hidden=true;$('workbench').hidden=false;
    $('node-name').textContent=S.session.host;$('auth-badge').textContent=S.session.mode==='open'?'Token-free':(S.session.mode==='cloudflare'?'Access verified':(S.session.public_origin?'Local + HTTPS':'Local setup'));
    $('operator-label').textContent=S.session.actor;
    $('ai-badge').textContent='Loading…';$('send-chat').disabled=true;
    await refreshAISettings();
    const [engs,inventory]=await Promise.all([api('/api/engagements'),api('/api/tools')]);
    S.engagements=engs;setInventory(inventory);renderEngagementOptions();
    const saved=sessionStorage.getItem('foxworx-eng:'+S.session.actor);
    await selectEngagement(engs.some(x=>x.id===saved)?saved:engs[0]?.id);
    renderNode(S.session);
    await petUI.refresh({quiet:true});
    await petUI.refreshChat({quiet:true});
  }catch(e){$('login-loading').hidden=true;$('login-error').textContent=e.message;if(!$('workbench').hidden)toast('Initialization incomplete: '+e.message+' Reload after checking the node.');}
}
$('login-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;$('login-error').textContent='';try{await api('/api/login','POST',{token:$('setup-token').value,remember:$('remember-browser').checked});$('setup-token').value='';await boot();}catch(e){$('login-error').textContent=e.message;}finally{b.disabled=false;}};

function renderEngagementOptions(){const select=$('engagement-select');select.replaceChildren(...S.engagements.map(x=>option(x.id,x.name)));if(S.eng)select.value=S.eng;}
async function selectEngagement(id){
  if(!id)return;disconnectTerminal();S.terminalId='';S.selectedJob='';S.outputOffset=0;S.outputText='';S.eng=id;
  $('engagement-select').value=id;sessionStorage.setItem('foxworx-eng:'+S.session.actor,id);
  const eng=currentEng();$('scope-summary').textContent=eng.include.join(' · ');$('scope-summary').title=eng.include.join('\n');
  resetJobSelection();
  $('ai-job').replaceChildren(option('','No job selected'));$('share-output').checked=false;
  stopRabbitPolling();S.rabbitRun=null;S.graph?.setEngagement(id);
  await Promise.all([refreshJobs(),refreshTerminals(),refreshFiles(),refreshChat(),refreshRabbit()]);
  if(S.view==='team')await refreshTeam();
  const saved=sessionStorage.getItem('foxworx-term:'+S.session.actor+':'+S.eng);
  if(saved && [...$('terminal-select').options].some(o=>o.value===saved)){
    $('terminal-select').value=saved;await connectTerminal(saved);
  }else{resetTerminalView();}
}
$('engagement-select').onchange=handle(e=>selectEngagement(e.target.value));
function editEngagement(existing){S.editingEngagement=existing?.id || '';$('engagement-title').textContent=existing?'Scope & notes':'New engagement';$('eng-name').value=existing?.name || '';$('eng-include').value=existing?.include.join('\n') || '';$('eng-exclude').value=existing?.exclude?.join('\n') || '';$('eng-url').value=existing?.program_url || '';$('eng-team-key').value=existing?.team_key || '';$('eng-notes').value=existing?.notes || '';$('eng-error').textContent='';openDialog('engagement-dialog');}
$('new-engagement').onclick=()=>editEngagement();$('edit-engagement').onclick=()=>editEngagement(currentEng());
$('engagement-form').onsubmit=async e=>{e.preventDefault();e.submitter.disabled=true;$('eng-error').textContent='';try{
  const lines=id=>$(id).value.split('\n').map(x=>x.trim()).filter(Boolean);
  const value={name:$('eng-name').value.trim(),include:lines('eng-include'),exclude:lines('eng-exclude'),program_url:$('eng-url').value.trim(),team_key:$('eng-team-key').value.trim(),notes:$('eng-notes').value};
  const result=await api('/api/engagements'+(S.editingEngagement?'/'+S.editingEngagement:''),S.editingEngagement?'PUT':'POST',value);
  S.engagements=await api('/api/engagements');renderEngagementOptions();$('engagement-dialog').close();await selectEngagement(result.id);toast('Engagement saved. Pending commands must use the current scope.');
}catch(err){$('eng-error').textContent=err.message;}finally{e.submitter.disabled=false;}};

function setInventory(data){S.tools=data.tools;S.profiles=data.profiles;const old=$('category-filter').value;$('category-filter').replaceChildren(option('','All categories'),...Array.from(new Set(S.tools.map(t=>t.category))).sort().map(x=>option(x,x)));$('category-filter').value=old;renderTools();}
function renderTools(){
  const query=$('tool-search').value.toLowerCase(),cat=$('category-filter').value,filter=$('availability-filter').value;
  const items=S.tools.filter(t=>(filter==='all'||filter==='installed'&&t.installed||filter==='curated'&&t.curated)&&(!cat||cat===t.category)&&(!query||(t.name+' '+t.description+' '+t.category).toLowerCase().includes(query)));
  $('tool-count').textContent=`${items.length} matches · ${S.tools.filter(x=>x.installed).length} executables discovered`;
  $('tool-list').replaceChildren();
  for(const tool of items.slice(0,S.limit)){
    const card=text('button','',`tool-card${tool.installed?'':' missing'}`);card.type='button';
    card.append(text('span',tool.installed?(tool.mode==='unknown'?'unclassified':tool.mode):'missing','tool-mode'),text('strong',tool.name),text('span',tool.description,'tool-description'));
    card.onclick=()=>showTool(tool);$('tool-list').append(card);
  }
  if(!items.length)$('tool-list').append(text('p','No matching tools. Change filters or refresh after installing software.','hint'));
  $('more-tools').hidden=items.length<=S.limit;
}
for(const id of ['tool-search','category-filter','availability-filter'])$(id).addEventListener(id==='tool-search'?'input':'change',()=>{S.limit=80;renderTools();});
$('more-tools').onclick=()=>{S.limit+=80;renderTools();};
$('refresh-tools').onclick=handle(async()=>{$('refresh-tools').disabled=true;try{setInventory(await api('/api/tools/refresh','POST',{}));toast('Tool inventory refreshed. No binaries were executed for discovery.');}finally{$('refresh-tools').disabled=false;}});
function metadata(target,entries){target.replaceChildren();for(const [key,value] of entries){target.append(text('dt',key),text('dd',String(value || '—')));}}
function showTool(tool){
  S.tool=tool;document.body.classList.remove('tools-open');$('tool-title').textContent=tool.name;$('tool-category').textContent=tool.category;$('tool-description').textContent=tool.description;
  $('tool-status').textContent=tool.installed?(tool.mode==='gui'?'Desktop required — not displayed inside this workbench.':tool.mode==='interactive'?'Interactive tool — use the real terminal.':tool.mode==='unknown'?'Executable found — mode and dependencies have not been classified.':'Executable found — verify dependencies before use.'):'Not installed or not on the configured discovery PATH.';
  metadata($('tool-metadata'),[['Executable',tool.path],['Package',tool.package],['Package version',tool.version]]);
  $('tool-note').textContent=tool.note+(tool.installed?'':tool.package?` Install separately with your administrator: sudo apt install ${tool.package}`:' Install from the tool’s official distribution, then refresh inventory.');
  const profiles=Object.entries(S.profiles).filter(([,p])=>p.tool===tool.name);
  $('tool-profile').replaceChildren(...profiles.map(([id,p])=>option(id,p.label)),option('advanced','Advanced · literal arguments'));
  $('tool-target').value='';$('tool-args').value='';$('tool-error').textContent='';
  const runnable=tool.installed&&!['gui','interactive'].includes(tool.mode);
  $('tool-run-fields').hidden=!runnable;$('tool-prepare').hidden=!runnable;$('tool-insert').disabled=!tool.installed||tool.mode==='gui';
  $('tool-explain').disabled=!S.session.ai_configured;toggleProfile();openDialog('tool-dialog');
}
function toggleProfile(){const profile=$('tool-profile').value,advanced=profile==='advanced';$('args-field').hidden=!advanced;$('target-field').hidden=advanced;const canBind=S.tool?.name==='curl'&&['http-headers','http-options','http-status','http-get-limited'].includes(profile);$('tool-interface-field').hidden=!canBind;if(canBind)renderAssessmentOptions();else $('tool-interface').value='';}
$('tool-profile').onchange=toggleProfile;
$('tool-form').onsubmit=async e=>{e.preventDefault();$('tool-error').textContent='';$('tool-prepare').disabled=true;try{
  const profile=$('tool-profile').value;
  const args=profile==='advanced'?(await api('/api/arguments/parse','POST',{text:$('tool-args').value})).args:[];
  const proposal=await api('/api/proposals','POST',{engagement_id:S.eng,tool:S.tool.name,args,profile,target:$('tool-target').value.trim(),reason:'Operator-requested '+S.tool.name+' workflow',interface_name:$('tool-interface-field').hidden?'':$('tool-interface').value});
  $('tool-dialog').close();showApproval(proposal);await refreshJobs();
}catch(err){$('tool-error').textContent=err.message;}finally{$('tool-prepare').disabled=false;}};
// Knowledge is independently retrievable by operators and AI; it never changes
// the adapter policy or the approved execution scope.
let intelName=''; let intelOnline=false;
const inteldoc=(tag,value,cls='')=>text(tag,value,cls);
async function searchIntelligence(){
  const term=$('intel-search').value.trim();
  const result=await api('/api/tool-intelligence?query='+encodeURIComponent(term));
  intelOnline=!!result.online_enabled;
  $('intel-result-count').textContent=`${result.tools.length} discovered matches${result.tools.length>=60?' (showing first 60; refine search)':''}`;
  $('intel-results').replaceChildren();
  for(const tool of result.tools){
    const b=inteldoc('button','',`intel-tool${tool.name===intelName?' selected':''}`);
    b.type='button';b.append(inteldoc('strong',tool.name),inteldoc('small',tool.description));
    b.onclick=()=>loadKnowledge(tool.name).catch(e=>toast(e.message));$('intel-results').append(b);
  }
  if(!result.tools.length)$('intel-results').append(inteldoc('p','No installed tools matched. Try a different name or refresh the toolbox.','hint'));
  $('intel-online').disabled=!intelOnline||!intelName;
  $('intel-search-web').disabled=!intelOnline||!intelName;
}
async function loadKnowledge(name,method='GET',route=''){
  intelName=name;
  const path='/api/tool-intelligence/'+encodeURIComponent(name);
  $('intel-toolname').textContent=name;
  $('intel-status').textContent='Reading version-matched documentation…';
  const result=await api(path+route,method,method==='GET'?undefined:{});
  const detail=(result.documents===undefined)?await api(path):result;
  if(name!==intelName)return;
  $('intel-status').textContent=`${detail.cached?'Cached':'Fresh'} local documentation · ${detail.version||'unreported package version'} · executable verified · no command run`;
  $('intel-metadata').textContent=`${detail.path} · ${detail.category} · ${detail.mode}`;
  $('intel-flags').replaceChildren(...detail.flags.slice(0,70).map(flag=>inteldoc('code',flag,'intel-flag')));
  if(!detail.flags.length)$('intel-flags').append(inteldoc('p','No CLI flags indexed. This tool may lack a local manual.','hint'));
  $('intel-docs').replaceChildren();
  for(const doc of detail.documents){
    const section=inteldoc('div','','intel-document');
    section.append(inteldoc('strong',`${doc.source} · ${doc.expired?'stale':'cached'} · untrusted reference`),
                   inteldoc('small',doc.location));
    const pre=inteldoc('pre',doc.excerpt.slice(0,12000));pre.tabIndex=0;section.append(pre);
    $('intel-docs').append(section);
  }
  if(!detail.documents.length)$('intel-docs').append(inteldoc('p','No installed man/package page found. Consult official documentation if permitted.','hint'));
  $('intel-notes').replaceChildren(...detail.notes.map(note=>inteldoc('p',`[${note.author}] ${note.note}`,'intel-note-item')));
  if(!detail.notes.length)$('intel-notes').append(inteldoc('p','No operator-verified notes yet.','hint'));
  for(const id of ['intel-refresh','intel-save-note'])$(id).disabled=false;
  for(const id of ['intel-online','intel-search-web'])$(id).disabled=!intelOnline;
  for(const b of $('intel-results').querySelectorAll('button'))b.classList.toggle('selected',b.querySelector('strong')?.textContent===name);
}
$('intel-find').onclick=handle(searchIntelligence);
$('intel-search').addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();searchIntelligence().catch(e=>toast(e.message));}});
$('intel-refresh').onclick=handle(async()=>loadKnowledge(intelName,'POST','/refresh'));
$('intel-online').onclick=handle(async()=>{
  const result=await api('/api/tool-intelligence/'+encodeURIComponent(intelName)+'/research','POST',{});
  await loadKnowledge(intelName);
  toast(`Official Kali documentation ${result.cached?'loaded from cache':'cached'} for ${intelName}.`);
});
$('intel-search-web').onclick=handle(async()=>{
  const name=intelName;
  const result=await api('/api/tool-intelligence/'+encodeURIComponent(name)+'/search','POST',{});
  if(name!==intelName)return;
  const wrapper=inteldoc('div','','intel-document');wrapper.append(inteldoc('strong','Approved external documentation links · untrusted search results'));
  for(const hit of result.results){
    const row=inteldoc('p','');const a=inteldoc('a',hit.title||hit.url);
    try{const u=new URL(hit.url);if(u.protocol!=='https:'||!['www.kali.org','manpages.debian.org','www.gnu.org','github.com'].includes(u.hostname)||u.username||u.password||u.port)continue;}
    catch{continue;}
    a.href=hit.url;a.target='_blank';a.rel='noopener noreferrer';row.append(a,inteldoc('small',' · '+hit.description));wrapper.append(row);
  }
  if(!result.results.length)wrapper.append(inteldoc('p','No approved results found.','hint'));
  $('intel-docs').prepend(wrapper);
});
$('intel-save-note').onclick=handle(async()=>{
  if(!intelName)return;const note=$('intel-note').value.trim();
  if(note.length<3||note.length>600){toast('Enter a note between 3 and 600 characters.');return;}
  await api('/api/tool-intelligence/'+encodeURIComponent(intelName)+'/notes','POST',{note});
  $('intel-note').value='';await loadKnowledge(intelName);toast('Version-specific note saved.');
});
$('tool-knowledge').onclick=handle(async()=>{
  const name=S.tool?.name;if(!name)return;
  $('tool-dialog').close();switchTab('intelligence');$('intel-search').value=name;
  await searchIntelligence();await loadKnowledge(name);
});
$('tool-explain').onclick=()=>{$('tool-dialog').close();$('chat-input').value=`Explain ${S.tool.name}, common safe starting options, its prerequisites, and how to interpret its output. Do not run anything.`;$('ai-mode').value='tutor';$('chat-input').focus();};
$('tool-insert').onclick=handle(async()=>{const tool=S.tool;$('tool-dialog').close();switchTab('terminal');if(!S.terminalId)await newTerminal();else if(!S.ws||S.ws.readyState!==WebSocket.OPEN)await connectTerminal(S.terminalId);if(!S.ws||S.ws.readyState!==WebSocket.OPEN){toast('Connect the terminal, then insert the tool name again.');return;}sendInput(shellQuote(tool.path)+' ');S.term.focus();toast('Tool name inserted only. Add arguments and press Enter when ready.');});

function showApproval(proposal){S.proposal=proposal;$('approval-check').checked=false;$('approve-run').disabled=true;$('approval-error').textContent='';$('approval-command').textContent=proposal.command;$('approval-reason').textContent=proposal.reason;
  $('approval-scope').textContent=`${currentEng()?.name || 'Engagement'} · ${proposal.scope_check==='input-checked'?'Guided target passed input-scope validation':proposal.scope_check==='admin-template-input-checked'?'Administrator-registered command · target input checked; network scope not isolated':'Advanced command: scope and traffic require manual review'}`;
  $('approval-warnings').replaceChildren(...proposal.warnings.filter(Boolean).map(w=>text('p',w)));
  $('approval-expiry').textContent=`Proposal expires ${new Date(proposal.expires*1000).toLocaleTimeString()}. Timeout: ${proposal.timeout}s. One approval permits one execution.`;
  openDialog('approval-dialog');
}
$('approval-check').onchange=()=>{$('approve-run').disabled=!$('approval-check').checked;};
$('copy-command').onclick=()=>copy(S.proposal?.command);
$('dismiss-proposal').onclick=handle(async()=>{await api(`/api/proposals/${S.proposal.id}/dismiss`,'POST',{});$('approval-dialog').close();await refreshJobs();});
$('approval-form').onsubmit=async e=>{e.preventDefault();if(!$('approval-check').checked)return;$('approve-run').disabled=true;$('approval-error').textContent='';try{
  const job=await api(`/api/proposals/${S.proposal.id}/approve`,'POST',{digest:S.proposal.digest,authorized:true});
  $('approval-dialog').close();switchTab('jobs');await refreshJobs();await selectJob(job.id);toast('Job accepted. Watch the recorded status and output; acceptance does not mean success.');
}catch(err){$('approval-error').textContent=err.message;await refreshJobs();}finally{$('approve-run').disabled=!$('approval-check').checked;}};

function switchTab(view){S.view=view;for(const name of ['terminal','intelligence','team','graph','jobs','evidence','hardware','node','pet']){$('view-'+name).hidden=name!==view;$('tab-'+name).setAttribute('aria-selected',String(name===view));}if(view==='terminal')requestAnimationFrame(()=>S.fit?.fit());if(view==='intelligence'&&!intelName)searchIntelligence().catch(e=>toast(e.message));if(view==='team')refreshTeam().catch(e=>toast(e.message));if(view==='evidence')refreshFiles().catch(e=>toast(e.message));if(view==='graph')S.graph?.refresh(S.eng);if(view==='hardware')refreshHardware().catch(e=>toast(e.message));if(view==='node')refreshNode().catch(e=>toast(e.message));if(view==='pet')petUI.refresh({quiet:true}).then(()=>petUI.refreshChat({quiet:true}));}
document.querySelectorAll('[data-tab]').forEach(b=>{b.onclick=()=>switchTab(b.dataset.tab);b.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const tabs=[...document.querySelectorAll('[data-tab]')];const next=tabs[(tabs.indexOf(b)+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length];next.focus();next.click();}});});
async function refreshJobs(){
  if(!S.eng)return;const eid=S.eng;const [jobs,proposals]=await Promise.all([api('/api/jobs?engagement_id='+eid),api('/api/proposals?engagement_id='+eid)]);if(eid!==S.eng)return;
  S.jobs=jobs;$('job-count').textContent=String(jobs.length);
  $('pending-proposals').replaceChildren();for(const p of proposals.filter(x=>x.status==='pending')){const row=text('div','','pending-row'),label=text('div',p.tool+' · awaiting approval');label.append(text('small',p.source==='ai'?'Proposed by AI · not executed':'Prepared by operator · not executed'));const b=text('button','Review');b.onclick=()=>showApproval(p);row.append(label,b);$('pending-proposals').append(row);}
  const y=$('job-list').scrollTop;$('job-list').replaceChildren();
  for(const job of jobs){const row=text('div','',`job-row${job.id===S.selectedJob?' selected':''}`),b=text('button',job.tool+' · '+job.id.slice(0,6));b.onclick=handle(()=>selectJob(job.id));row.append(b,text('span',prettyStatus(job.status),'job-status status-'+job.status));$('job-list').append(row);}
  if(!jobs.length)$('job-list').append(text('p','No jobs yet. Choose a tool or ask the copilot to prepare a command.','hint'));
  $('job-list').scrollTop=y;
  const choice=$('ai-job').value;$('ai-job').replaceChildren(option('','No job selected'),...jobs.map(j=>option(j.id,`${j.tool} · ${prettyStatus(j.status)} · ${j.id.slice(0,6)}`)));$('ai-job').value=jobs.some(j=>j.id===choice)?choice:'';
  if(S.selectedJob)await pollOutput();
}
function syncDeleteJob(job=S.jobs.find(j=>j.id===S.selectedJob)){
  $('delete-selected').disabled=Boolean(S.deletingJob)||!job||!finishedJob(job.status);
}
function resetJobSelection(){
  const previous=S.selectedJob;S.selectedJob='';S.outputOffset=0;S.outputText='';
  $('job-output').textContent='Select a job to inspect its output.';
  $('output-label').textContent='Select a job to inspect its output';
  $('output-note').textContent='Export captured logs from Evidence before deleting a job if you need to keep them.';
  $('stop-selected').disabled=true;$('delete-selected').disabled=true;
  if(previous&&$('ai-job').value===previous){$('ai-job').value='';$('share-output').checked=false;}
}
async function selectJob(id){S.selectedJob=id;S.outputOffset=0;S.outputText='';$('stop-selected').disabled=true;$('delete-selected').disabled=true;$('job-output').textContent='Waiting for output…';await pollOutput();for(const row of $('job-list').children)row.classList.toggle('selected',row.textContent.includes(id.slice(0,6)));}
function stripAnsi(value){return value.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g,'').replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g,'');}
async function pollOutput(){
  if(!S.selectedJob)return;const id=S.selectedJob;let r;
  try{
    for(let i=0;i<3;i++){r=await api(`/api/jobs/${id}/output?offset=${S.outputOffset}`);if(id!==S.selectedJob)return;S.outputOffset=r.offset;S.outputText=(S.outputText+stripAnsi(r.text)).slice(-300000);if(r.text.length<65000)break;}
  }catch(error){
    if(error.status===404){if(id===S.selectedJob){resetJobSelection();toast('This job is no longer available.');}return;}
    throw error;
  }
  $('job-output').textContent=S.outputText || (active(r.job.status)?'Running; no output captured yet.':'This job produced no text output.');
  $('output-label').textContent=`${r.job.tool} · ${prettyStatus(r.job.status)}${r.job.returncode!==null?' · exit '+r.job.returncode:''}`;
  $('stop-selected').disabled=!active(r.job.status);$('output-note').textContent=r.job.error || 'Visible window: at most 300,000 characters. Raw stdout and stderr are preserved in evidence exports.';
  syncDeleteJob(r.job);
  if($('follow-output').checked)$('job-output').scrollTop=$('job-output').scrollHeight;
}
$('refresh-jobs').onclick=handle(refreshJobs);$('copy-output').onclick=()=>copy(S.outputText);
$('job-to-ai').onclick=()=>{if(!S.selectedJob)return toast('Select a job first.');$('ai-job').value=S.selectedJob;$('share-output').checked=false;$('chat-input').focus();toast('Job selected as context. Check “Share” only after reviewing the output.');};
$('stop-selected').onclick=handle(async()=>{if(S.selectedJob){await api(`/api/jobs/${S.selectedJob}/stop`,'POST',{});await refreshJobs();}});
$('delete-selected').onclick=handle(async()=>{
  const id=S.selectedJob,eid=S.eng;
  if(!id||S.deletingJob)return;
  if(!confirm('Permanently delete this job and its captured stdout/stderr logs? This cannot be undone. Export evidence first if you need to keep the logs.'))return;
  S.deletingJob=id;syncDeleteJob();
  try{
    await api(`/api/jobs/${id}`,'DELETE',{});
    if(S.selectedJob===id)resetJobSelection();
    if($('ai-job').value===id){$('ai-job').value='';$('share-output').checked=false;}
    if(S.eng===eid)await Promise.all([refreshJobs(),refreshRabbit()]);
    toast('Job and captured logs deleted.');
  }finally{S.deletingJob='';syncDeleteJob();}
});
$('stop-all').onclick=handle(async()=>{if(!confirm('Stop all of your managed jobs on this node? Terminal sessions are separate and will remain open.'))return;const r=await api('/api/jobs-stop-all','POST',{});await refreshJobs();toast(`${r.requested} stop requests issued. Terminal sessions were not closed.`);});

function terminalKey(){return 'foxworx-term:'+S.session.actor+':'+S.eng;}
function ensureTerminal(){$('terminal-scroll-controls').hidden=false;if(S.term)return;S.term=new Terminal({cursorBlink:true,scrollback:3000,fontSize:Number(localStorage.getItem('foxworx-font')||14),fontFamily:'ui-monospace, Consolas, monospace',theme:{background:'#0b1018',foreground:'#dce5f1',cursor:'#ffaf62'}});S.fit=new FitAddon();S.term.loadAddon(S.fit);$('terminal').hidden=false;S.term.open($('terminal'));S.term.parser.registerOscHandler(52,()=>true);bindTerminalScroll(S.term);
  S.term.onData(data=>sendInput(data));S.term.onResize(({rows,cols})=>{if(S.ws?.readyState===WebSocket.OPEN)S.ws.send(JSON.stringify({type:'resize',rows,cols}));});
  S.term.attachCustomKeyEventHandler(e=>{if(e.type==='keydown'&&e.ctrlKey&&e.shiftKey&&e.code==='KeyC'){copy(S.term.getSelection());return false;}return true;});
  new ResizeObserver(()=>{try{S.fit.fit();}catch{}}).observe($('terminal-wrap'));
  $('terminal').addEventListener('paste',e=>{const value=e.clipboardData?.getData('text')||'';if(/[\r\n]/.test(value)&&!confirm('This paste contains multiple lines and may execute commands immediately. Paste it into the real shell?')){e.preventDefault();e.stopImmediatePropagation();}},true);
}
function resetTerminalView(){S.terminalId='';$('terminal-empty').hidden=false;$('terminal').hidden=true;$('terminal-scroll-controls').hidden=true;$('terminal-state').textContent='No terminal connected';$('close-terminal').disabled=true;$('reconnect-terminal').disabled=true;}
function disconnectTerminal(){clearTimeout(S.reconnectTimer);S.reconnectTimer=null;const old=S.ws;S.ws=null;if(old)old.close();}
function sendInput(data){if(S.ws?.readyState===WebSocket.OPEN)S.ws.send(JSON.stringify({type:'input',data}));else toast('Terminal is disconnected. Reconnect before entering commands; your input was not sent.');}
async function refreshTerminals(){const eid=S.eng;const rows=await api('/api/terminals');if(eid!==S.eng)return;const previous=S.terminalId || $('terminal-select').value;$('terminal-select').replaceChildren(option('','Choose a session'),...rows.filter(t=>t.engagement_id===eid).map(t=>option(t.id,`${t.status==='running'?'Shell':'Exited'} · ${t.id.slice(0,6)}`)));if(rows.some(t=>t.id===previous&&t.engagement_id===eid))$('terminal-select').value=previous;}
async function newTerminal(){const value=await api('/api/terminals','POST',{engagement_id:S.eng});await refreshTerminals();$('terminal-select').value=value.id;await connectTerminal(value.id);}
async function connectTerminal(id){
  if(!id)return;disconnectTerminal();S.terminalId=id;sessionStorage.setItem(terminalKey(),id);$('terminal-empty').hidden=true;$('terminal').hidden=false;ensureTerminal();S.term.reset();$('terminal-state').textContent='Connecting…';$('close-terminal').disabled=false;$('reconnect-terminal').disabled=false;
  const {ticket}=await api(`/api/terminals/${id}/ticket`,'POST',{});
  const protocol=location.protocol==='https:'?'wss:':'ws:';
  const ws=new WebSocket(`${protocol}//${location.host}/ws/terminals/${id}?ticket=${encodeURIComponent(ticket)}`);S.ws=ws;let retry=true;
  await new Promise((resolve,reject)=>{
    let ready=false;
    ws.onopen=()=>{ready=true;S.reconnectTries=0;$('terminal-state').textContent='Connected · real shell';requestAnimationFrame(()=>{S.fit.fit();ws.send(JSON.stringify({type:'resize',rows:S.term.rows,cols:S.term.cols}));S.term.focus();});resolve();};
    ws.onmessage=e=>{if(S.ws!==ws)return;let msg;try{msg=JSON.parse(e.data);}catch{return;}
      if(msg.type==='output')S.term.write(Uint8Array.from(atob(msg.data),c=>c.charCodeAt(0)));
      else if(msg.type==='ping')ws.send(JSON.stringify({type:'pong'}));
      else if(msg.type==='ready'&&msg.history_truncated)toast('Reconnected with the latest terminal buffer; older scrollback is not retained.');
      else if(['exit','closed','gap'].includes(msg.type)){retry=msg.type==='gap';$('terminal-state').textContent=msg.message||`Shell exited with code ${msg.returncode}.`;$('announcer').textContent=$('terminal-state').textContent;ws.close();refreshTerminals().catch(()=>{});}
    };
    ws.onerror=()=>{if(!ready)reject(new Error('Terminal connection failed. Verify Cloudflare Access and WebSocket routing.'));};
    ws.onclose=()=>{if(!ready)reject(new Error('Terminal connection was rejected. Reauthenticate and check the configured origin.'));if(S.ws!==ws)return;S.ws=null;if(retry&&S.terminalId===id){$('terminal-state').textContent='Disconnected · shell may still be running';if(S.reconnectTries<5){const delay=Math.min(15000,1000*2**S.reconnectTries++);S.reconnectTimer=setTimeout(()=>connectTerminal(id).catch(e=>{toast(e.message);$('terminal-state').textContent='Reconnect needed · check authentication';}),delay);}}};
  });
}
$('new-terminal').onclick=handle(newTerminal);$('first-terminal').onclick=handle(newTerminal);$('reconnect-terminal').onclick=handle(()=>connectTerminal($('terminal-select').value||S.terminalId));
$('terminal-select').onchange=handle(async e=>{if(e.target.value)await connectTerminal(e.target.value);else{disconnectTerminal();resetTerminalView();}});
$('close-terminal').onclick=handle(async()=>{if(!S.terminalId||!confirm('Close this terminal and stop its shell-session processes? Managed jobs are separate.'))return;const id=S.terminalId;disconnectTerminal();await api('/api/terminals/'+id,'DELETE',{});sessionStorage.removeItem(terminalKey());resetTerminalView();await refreshTerminals();});
for(const [id,delta] of [['font-down',-1],['font-up',1]])$(id).onclick=()=>{const size=Math.max(11,Math.min(24,Number(localStorage.getItem('foxworx-font')||14)+delta));localStorage.setItem('foxworx-font',size);if(S.term){S.term.options.fontSize=size;S.fit.fit();}};
$('copy-selection').onclick=()=>copy(S.term?.getSelection());$('selection-to-ai').onclick=()=>{const value=S.term?.getSelection();if(!value)return toast('Select terminal text first.');$('chat-input').value=('Help interpret this untrusted terminal excerpt:\n'+value).slice(0,12000);$('chat-input').focus();toast('Selection added to the draft only. Review it before sending.');};

async function refreshChat(){const eid=S.eng;const messages=await api('/api/chat?engagement_id='+eid);if(eid!==S.eng)return;$('chat-messages').replaceChildren();for(const m of messages)addMessage(m.role,m.text);if(!messages.length)$('chat-messages').append(text('div','Describe your objective. The copilot can explain tools and prepare reviewable proposals; it cannot approve them.','chat-empty'));}
function addMessage(role,value,proposals=[]){const empty=$('chat-messages').querySelector('.chat-empty');empty?.remove();const message=text('div','','message '+role);message.append(text('span',role==='user'?'You':'FOXWORX','speaker'),text('span',value));for(const p of proposals){const b=text('button','Review '+p.tool+' proposal','primary');b.onclick=()=>showApproval(p);message.append(b);}$('chat-messages').append(message);$('chat-messages').scrollTop=$('chat-messages').scrollHeight;}
function rabbitMode(){return $('ai-mode').value==='rabbit';}
function selectedCodex(){return S.aiSettings?.selected.provider==='codex';}
function updateRabbitMode(){
  $('rabbit-config').hidden=!rabbitMode();
  $('rabbit-progress').hidden=!rabbitMode()||!S.rabbitRun;
  if(rabbitMode())refreshAdapterPolicy().catch(error=>toast(error.message));
  if(S.eng)refreshChat().catch(()=>{});
  $('chat-context').hidden=rabbitMode();
  $('chat-messages').hidden=rabbitMode();
  $('clear-chat').title='Clear saved chat for this engagement';
  document.querySelector('.copilot').classList.toggle('rabbit-mode',rabbitMode());
  document.querySelector('.copilot .eyebrow').textContent=rabbitMode()?'EXPLORE · RETRY · REPORT':$('ai-mode').value==='tutor'?'ASK · LEARN · UNDERSTAND':'EXPLAIN · PROPOSE · REVIEW';
  $('chat-input').placeholder=rabbitMode()?'Describe a specific objective for the authorized target…':'Describe your objective or ask about a tool…';
  syncRabbitSubmit();
}
async function refreshAdapterPolicy(){
  const button=$('rabbit-policy-refresh');button.disabled=true;
  try{
    const data=await api('/api/adapter-policy');S.rabbitPolicy=data;
    const list=$('rabbit-adapter-list');list.replaceChildren();
    $('rabbit-policy-status').textContent=data.status==='active'
      ?`Root-owned policy active · ${data.profiles.filter(x=>x.enabled).length} enabled · ${data.profiles.filter(x=>x.available).length} installed and available · ${data.max_steps} decisions / ${data.max_minutes} minutes maximum`
      :`No trusted administrator policy (${data.status}). Rabbit Hole execution is disabled until an administrator installs /etc/foxworx/adapter-policy.json.`;
    for(const profile of data.profiles){
      const row=text('div','','rabbit-adapter-row');
      const label=text('label','','check rabbit-adapter');
      const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.name='rabbit-profile';checkbox.value=profile.profile;
      checkbox.disabled=!profile.available;
      checkbox.checked=profile.available && ['tcp-connect','dns-a'].includes(profile.profile);
      const category=profile.mode==='review'?' · REVIEW REQUIRED':profile.risk==='active'?' · ACTIVE':' · RECON';
      const reason=!profile.enabled?' · disabled by administrator':!profile.installed?' · not installed':'';
      label.append(checkbox,text('span',`${profile.tool} · ${profile.label}${category}${reason}`));
      label.title=profile.hint;
      row.append(label);
      if(profile.review_available){
        const review=text('button','Preview command','tiny');review.type='button';
        review.title='Prepare a command for one-time human review. Does not execute.';
        review.onclick=handle(async()=>{
          if(!S.eng)throw new Error('Choose an engagement first.');
          const target=$('rabbit-target').value.trim();
          if(!target)throw new Error('Enter the exact authorized target before previewing.');
          const proposal=await api('/api/registered-proposals','POST',{
            engagement_id:S.eng,profile:profile.profile,target,parameters:{},reason:'Operator-requested reviewed adapter: '+profile.label});
          showApproval(proposal);await refreshJobs();
        });
        row.append(review);
      }
      row.dataset.search=`${profile.tool} ${profile.label} ${profile.profile} ${profile.risk||''} ${profile.mode||''}`.toLowerCase();
      list.append(row);
    }
    filterRabbitAdapters();
    $('rabbit-steps').max=String(data.max_steps||16);
    $('rabbit-minutes').max=String(data.max_minutes||30);
    if(data.status==='active'){
      $('rabbit-steps').value=String(Math.min(Number($('rabbit-steps').value)||8,data.max_steps));
      $('rabbit-minutes').value=String(Math.min(Number($('rabbit-minutes').value)||15,data.max_minutes));
    }
    $('rabbit-authorized').checked=false;
    syncRabbitSubmit();
  }catch(error){
    S.rabbitPolicy=null;
    $('rabbit-policy-status').textContent='Adapter policy is unavailable: '+error.message;
    $('rabbit-adapter-list').replaceChildren();
    syncRabbitSubmit();throw error;
  }finally{button.disabled=false;}
}
function filterRabbitAdapters(){
  const term=$('rabbit-adapter-search').value.trim().toLowerCase();
  for(const row of $('rabbit-adapter-list').children)row.hidden=Boolean(term)&&!row.dataset.search.includes(term);
}
$('rabbit-adapter-search').addEventListener('input',filterRabbitAdapters);
$('rabbit-policy-refresh').onclick=handle(refreshAdapterPolicy);

async function refreshCodexStatus(){
  const info=await api('/api/codex/status');S.codex={...S.codex,...info};
  $('codex-badge').textContent=!info.installed?'Not installed':info.connected?'ChatGPT connected':info.login?.pending?'Sign-in pending':'Not signed in';
  $('codex-status').textContent=!info.installed?'Install official @openai/codex on the node, and make it available on FOXWORX’s tool path.':info.connected?`Signed in via Codex${info.plan?' · '+info.plan+' plan':''}${info.email?' · '+info.email:''}. Used by the selected assistance mode.`:info.login?.pending?'Complete the device login on OpenAI’s site. This status refreshes automatically.':info.login?.error||'Sign in to Codex using your own ChatGPT account. A supported plan and available usage are required to run requests.';
  $('codex-signin').hidden=!info.installed||info.connected;
  $('codex-signout').hidden=!info.connected;
  $('codex-signin').disabled=!!info.busy||!!info.login?.pending;
  $('codex-signout').disabled=!!info.busy;
  $('codex-stop').hidden=!info.busy;
  if(info.connected||info.login?.success){$('codex-device').hidden=true;$('codex-user-code').textContent='';$('codex-verify-url').removeAttribute('href');}
  if(selectedCodex()){
    const selection=S.aiSettings.selected,status=await api('/api/ai/settings');
    if(selectedCodex()&&S.aiSettings.selected===selection)applyAIReadiness(status);
  }
  syncRabbitSubmit();return info;
}
$('codex-refresh').onclick=handle(refreshCodexStatus);
$('codex-signin').onclick=handle(async()=>{
  $('codex-signin').disabled=true;
  try{
    const result=await api('/api/codex/login','POST',{});
    $('codex-verify-url').href=result.verification_url;
    $('codex-verify-url').textContent='Open '+new URL(result.verification_url).hostname+' ↗';
    $('codex-user-code').textContent=result.user_code;
    $('codex-device').hidden=false;
    $('codex-status').textContent='Sign-in requested. Complete authorization on the official OpenAI verification page.';
    S.codex.connected=false;
  }finally{await refreshCodexStatus();}
});
$('codex-stop').onclick=handle(async()=>{
  $('codex-stop').disabled=true;
  try{await api('/api/codex/interrupt','POST',{});toast('Codex interruption requested.');}
  finally{$('codex-stop').disabled=false;}
});
$('codex-signout').onclick=handle(async()=>{
  if(!confirm('Disconnect this operator’s Codex ChatGPT account on this Kali host?'))return;
  await api('/api/codex/logout','POST',{});
  $('codex-device').hidden=true;$('codex-user-code').textContent='';$('codex-verify-url').removeAttribute('href');
  await refreshCodexStatus();toast('Codex ChatGPT account disconnected from this FOXWORX profile.');
});

$('ai-mode').addEventListener('change',updateRabbitMode);
function stopRabbitPolling(){if(S.rabbitTimer){clearInterval(S.rabbitTimer);S.rabbitTimer=null;}}
function syncRabbitSubmit(){
  const running=rabbitMode()&&S.rabbitRun&&['queued','running','stopping'].includes(S.rabbitRun.status);
  $('send-chat').textContent=running?'Run in progress':rabbitMode()?'Authorize & run':'Send';
  $('send-chat').disabled=S.chatBusy||Boolean(running)||(!S.session?.ai_configured||(selectedCodex()&&S.codex.busy)||(rabbitMode()&&S.rabbitPolicy?.status!=='active'));
}
function renderRabbit(run){
  if(!run){$('rabbit-progress').hidden=true;document.querySelector('.copilot').classList.remove('rabbit-active');syncRabbitSubmit();return;}
  S.rabbitRun=run;$('rabbit-progress').hidden=!rabbitMode();
  document.querySelector('.copilot').classList.toggle('rabbit-active',['queued','running','stopping'].includes(run.status));
  $('rabbit-run-title').textContent='↪ '+(run.objective||'Rabbit Hole').slice(0,100);
  $('rabbit-run-status').textContent=prettyStatus(run.status);
  $('rabbit-run-budget').textContent=`Target: ${run.target} · ${run.steps.length}/${run.max_steps} decisions · up to ${run.max_minutes} minutes · ${run.provider}/${run.model}`;
  $('rabbit-run-summary').textContent=run.summary||'The model is evaluating the next authorized step…';
  $('rabbit-run-next').textContent=run.next_steps||'';
  $('rabbit-stop').hidden=!['queued','running','stopping'].includes(run.status);
  syncRabbitSubmit();
  const container=$('rabbit-steps-list');container.replaceChildren();
  for(const step of run.steps){
    const el=text('div',`#${step.number} · ${step.profile} · ${prettyStatus(step.status)}${step.detail?' · '+step.detail:''}`,'rabbit-step');
    if(step.job_id&&!step.job_deleted){const a=text('a','Inspect job →');a.href='#';a.onclick=async e=>{e.preventDefault();try{await refreshJobs();await selectJob(step.job_id);}catch(err){toast(err.message);}};el.append(a);}
    else if(step.job_deleted)el.append(text('span','Job and captured logs deleted','hint'));
    container.append(el);
  }
}
async function refreshRabbit(){
  if(!S.eng)return;
  const eid=S.eng,runs=await api('/api/rabbit-runs?engagement_id='+encodeURIComponent(eid));
  if(eid!==S.eng)return;
  const selected=runs.find(r=>['running','queued','stopping'].includes(r.status))||runs[0];
  renderRabbit(selected||null);
  stopRabbitPolling();
  if(selected&&['running','queued','stopping'].includes(selected.status)){
    S.rabbitTimer=setInterval(async()=>{
      if(!S.rabbitRun||S.eng!==eid){stopRabbitPolling();return;}
      try{const latest=await api('/api/rabbit-runs/'+S.rabbitRun.id);if(S.eng!==eid)return;renderRabbit(latest);
        if(!['running','queued','stopping'].includes(latest.status)){stopRabbitPolling();await refreshJobs();}
      }catch(err){stopRabbitPolling();toast('Rabbit Hole progress unavailable: '+err.message);}
    },2500);
  }
}
$('rabbit-stop').onclick=handle(async()=>{
  if(!S.rabbitRun)return;
  $('rabbit-stop').disabled=true;
  try{renderRabbit(await api('/api/rabbit-runs/'+S.rabbitRun.id+'/stop','POST',{}));await refreshRabbit();}
  finally{$('rabbit-stop').disabled=false;}
});
updateRabbitMode();
$('chat-form').onsubmit=async e=>{e.preventDefault();if(S.chatBusy)return;const value=$('chat-input').value.trim(),eid=S.eng;if(!value)return;
  if(rabbitMode() && !S.session.ai_configured)return toast('Configure an AI model before Rabbit Hole mode.');
  S.chatBusy=true;$('send-chat').disabled=true;$('send-chat').textContent=rabbitMode()?'Starting…':'Working…';
  try{
    if(rabbitMode()){
      const profiles=[...document.querySelectorAll('input[name="rabbit-profile"]:checked')].map(x=>x.value);
      if(S.rabbitPolicy?.status!=='active')throw new Error('A trusted administrator policy is required before Rabbit Hole can run.');
      if(!profiles.length)throw new Error('Select at least one installed, administrator-enabled workflow.');
      const payload={engagement_id:eid,objective:value,target:$('rabbit-target').value.trim(),profiles,
        max_steps:Number($('rabbit-steps').value),max_minutes:Number($('rabbit-minutes').value),authorized:$('rabbit-authorized').checked};
      if(!payload.authorized)throw new Error('Approve the one-time engagement authorization before starting.');
      const started=await api('/api/rabbit-runs','POST',payload);
      $('rabbit-authorized').checked=false;
      if(eid===S.eng){$('chat-input').value='';renderRabbit(started);await refreshRabbit();toast('Rabbit Hole authorized. It will stop at the chosen limit or when finished.');}
      else toast('Rabbit Hole started in the previous engagement.');
    }else{
      const result=await api('/api/chat','POST',{engagement_id:eid,message:value,mode:$('ai-mode').value,job_id:$('ai-job').value||null,share_output:$('share-output').checked});
      if(eid===S.eng){addMessage('user',value);addMessage('assistant',result.answer,result.proposals);$('chat-input').value='';await refreshJobs();}
      else toast('AI response saved in the previous engagement.');
    }
  }catch(err){toast(err.message+' Your draft is preserved.');}
  finally{S.chatBusy=false;syncRabbitSubmit();}
};
$('chat-input').onkeydown=e=>{if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();$('chat-form').requestSubmit();}};
$('clear-chat').onclick=handle(async()=>{if(confirm('Clear saved chat for this engagement? Job records and evidence will remain.')){await api('/api/chat?engagement_id='+S.eng,'DELETE',{});await refreshChat();}});

async function refreshFiles(){if(!S.eng)return;const eid=S.eng,result=await api(`/api/engagements/${eid}/files`);if(eid!==S.eng)return;$('file-summary').textContent=`${result.files.length} files${result.limited?' · listing capped at 1,000; use the terminal for the remainder':''}`;$('file-list').replaceChildren();for(const file of result.files){const row=text('div','','file-row'),a=text('a',file.path);a.href=`/api/engagements/${eid}/files/`+file.path.split('/').map(encodeURIComponent).join('/');a.download='';row.append(a,text('span',bytes(file.size),'muted'));$('file-list').append(row);}if(!result.files.length)$('file-list').append(text('p','No workspace files yet. Upload an authorized test artifact, or save tool output in the engagement directory.','hint'));}
$('refresh-files').onclick=handle(refreshFiles);
$('file-upload').onchange=handle(async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>10*1024*1024)throw new Error('Upload limit is 10 MiB. Transfer larger artifacts through an administrator-approved channel.');await api(`/api/engagements/${S.eng}/files`,'POST',file,{'X-Filename':encodeURIComponent(file.name),'Content-Type':'application/octet-stream'});await refreshFiles();toast('File uploaded without overwriting existing evidence.');}finally{e.target.value='';}});
$('export-evidence').onclick=handle(async()=>{const b=$('export-evidence');b.disabled=true;try{const r=await fetch(`/api/engagements/${S.eng}/export?files=${$('export-files').checked}`,{credentials:'same-origin',cache:'no-store'});if(!r.ok){const data=await r.json();throw new Error(explainError(data));}if(!r.headers.get('content-type')?.includes('application/zip'))throw new Error('Export returned an unexpected response. Reauthenticate before trying again.');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=`foxworx-${S.eng.slice(0,8)}-evidence.zip`;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);toast('Evidence export created. Review sensitive content before sharing.');}finally{b.disabled=false;}});
// Hardware is inventory-only until an operator chooses a role. No browser event
// can request radio mode changes, adapter resets, privileged commands or routes.
function renderAssessmentOptions(){
  const old=$('tool-interface').value;
  const allowed=(S.hardware?.networks||[]).filter(x=>x.role==='assessment'&&!x.protected);
  $('tool-interface').replaceChildren(option('','System default routing'),...allowed.map(x=>option(x.name,`${x.name} · ${x.type} · ${x.state}`)));
  if(allowed.some(x=>x.name===old))$('tool-interface').value=old;
}
function hardwareRow(title,details,tag=''){const card=text('div','','hardware-device');const header=text('div','','hardware-device-head');header.append(text('strong',title));if(tag)header.append(text('span',tag,'badge'));card.append(header,text('p',details,'hint'));return card;}
function renderHardware(report){
  S.hardware=report;
  const stat=$('hardware-stats');stat.replaceChildren();
  for(const [value,label] of [[report.summary.network_interfaces,'Network interfaces'],[report.summary.wireless_interfaces,'Wireless adapters'],[report.summary.pci_devices,'PCI devices'],[report.summary.usb_devices,'USB devices'],[report.summary.accelerators,'Kernel accelerators'],[report.summary.accelerator_candidates,'Possible accelerators']]){
    const card=text('div','','node-card');card.append(text('strong',value),text('small',label));stat.append(card);
  }
  $('hardware-network').replaceChildren();
  for(const nic of report.networks){
    const card=hardwareRow(`${nic.name} · ${nic.type}`,`State: ${nic.state} · Driver: ${nic.driver||'not reported'} · MTU: ${nic.mtu||'?'}${nic.wireless_phy?' · '+nic.wireless_phy:''} · Monitor: ${nic.monitor_mode} · Injection: ${nic.packet_injection}`,nic.protected?'PROTECTED':'role: '+nic.role);
    const controls=text('div','','hardware-actions');const select=document.createElement('select');select.setAttribute('aria-label','Role for '+nic.name);
    for(const role of ['unassigned','management','assessment','reserved'])select.append(option(role,role[0].toUpperCase()+role.slice(1)));
    select.value=nic.role;select.disabled=nic.protected;
    const save=text('button','Save role','tiny');save.type='button';save.disabled=nic.protected;
    save.onclick=handle(async()=>{if(select.value==='unassigned')throw new Error('Choose Management, Assessment or Reserved.');save.disabled=true;try{await api('/api/hardware/interfaces/'+encodeURIComponent(nic.name)+'/role','PUT',{role:select.value});await refreshHardware(true);toast('Role saved. It changes labeling and opt-in guided job selection only.');}finally{save.disabled=false;}});
    controls.append(select,save);card.append(controls);$('hardware-network').append(card);
  }
  if(!report.networks.length)$('hardware-network').append(text('p','No interfaces visible to this service. Check sysfs permissions and host networking.','hint'));
  $('hardware-compute').replaceChildren();
  for(const d of (report.nvidia||[]))$('hardware-compute').append(hardwareRow(`NVIDIA GPU ${d.index} · ${d.name}`,`${d.memory_mib} MiB VRAM · ${d.free_mib} MiB reported free · Driver ${d.driver_version||'unknown'}`,'NVIDIA'));
  for(const d of report.graphics)$('hardware-compute').append(hardwareRow('Graphics '+d.node,`Driver: ${d.device_driver||'unreported'} · DRM node visible, compute readiness unverified`));
  for(const d of report.accelerators)$('hardware-compute').append(hardwareRow('Accelerator '+d.node,d.status,'VISIBLE'));
  for(const d of report.accelerator_candidates)$('hardware-compute').append(hardwareRow('PCI '+d.id,'Possible compute accelerator, not verified NPU','CANDIDATE'));
  if(!(report.nvidia||[]).length&&!report.graphics.length&&!report.accelerators.length&&!report.accelerator_candidates.length)$('hardware-compute').append(text('p','No kernel graphics/accelerator interfaces found. Check Node for NVIDIA driver information.','hint'));
  renderHardwareBus();renderAssessmentOptions();
  $('hardware-categories').replaceChildren();
  for(const [name,value] of Object.entries(report.categories))$('hardware-categories').append(text('p',`${name}: ${value.count_visible}${value.truncated?'+':''} visible — ${value.names.slice(0,18).join(', ')}${value.names.length>18?' …':''}`,'hint'));
  $('hardware-note').textContent=report.warnings.join(' ');
}
function renderHardwareBus(){
  const query=$('hardware-filter').value.trim().toLowerCase(),report=S.hardware;
  if(!report)return;
  const bus=$('hardware-buses');bus.replaceChildren();let shown=0;
  for(const d of report.pci){const title=`PCI ${d.slot} · ${d.category}`,detail=`Vendor ${d.vendor_id} · Device ${d.device_id} · Driver ${d.driver||'unknown'} · Class ${d.class}`;
    if(query&&!(title+' '+detail).toLowerCase().includes(query))continue;
    if(shown++<100)bus.append(hardwareRow(title,detail));
  }
  for(const d of report.usb){const title=`USB ${d.port} · ${d.product||'Unknown product'}`,detail=`${d.manufacturer||'Unknown manufacturer'} · ${d.vendor_id}:${d.product_id} · ${d.speed_mbps||'?'} Mbps`;
    if(query&&!(title+' '+detail).toLowerCase().includes(query))continue;
    if(shown++<100)bus.append(hardwareRow(title,detail));
  }
  if(!shown)bus.append(text('p','No matching PCI or USB entries. Linux may not expose every device to this service.','hint'));
  if(shown>100)bus.append(text('p',`Showing first 100 of ${shown} matching records. Refine the filter to view others.`,'hint'));
}
async function refreshHardware(fresh=false){const report=await api('/api/hardware'+(fresh?'?fresh=true':''));renderHardware(report);}
$('hardware-refresh').onclick=handle(()=>refreshHardware(true));
$('hardware-filter').oninput=renderHardwareBus;
function renderNode(data){const h=data.hardware||{},g=h.gpus||[];$('resource-summary').textContent=`${bytes(data.free_disk_bytes)} free · ${data.active_jobs}/${data.max_jobs} jobs`;$('node-cards').replaceChildren();for(const [value,label] of [[data.architecture,'Architecture'],[`${h.gpu_count??0} NVIDIA`, 'GPU devices'],[bytes(data.free_disk_bytes),'Disk available'],[data.installed_executables,'Discovered executables'],[`${data.active_jobs} / ${data.max_jobs}`,'Managed jobs']]){const card=text('div','','node-card');card.append(text('strong',value),text('small',label));$('node-cards').append(card);}const dl=text('dl','','metadata');metadata(dl,[['Host',data.host],['Host profile',h.profile||'Unknown'],['Distribution',h.distro||'Unknown'],['Logical CPUs',h.cpu_count||'—'],['NVIDIA status',h.gpu_status||'Not checked'],['Local Ollama executable',h.ollama_installed?'Found':'Not found'],['GPU detail',g.length?g.map(x=>`${x.index}: ${x.name} (${x.memory_mib} MiB VRAM, ${x.free_mib} MiB free)`).join(' • '):'No NVIDIA devices reported'],['Auth mode',data.mode],['Linux UID',data.uid],['Python',data.python],['AI provider',data.ai_provider||'Not selected'],['AI model',data.ai_model||'Not configured'],['Curated tools',`${data.curated_installed} installed / ${data.curated_total} described`],['State',data.state_directory],['Configuration',data.config_file],['Job timeout',data.limits.job_timeout_seconds+' seconds'],['Per-job output',bytes(data.limits.job_log_bytes)]]);$('node-details').replaceChildren(dl,...([...data.warnings,...(h.warnings||[])]).map(w=>text('p',w,'notice')));}
async function refreshNode(){renderNode(await api('/api/diagnostics'));}
$('refresh-node').onclick=handle(refreshNode);$('load-audit').onclick=handle(async()=>{$('audit-output').textContent=(await api('/api/audit')).map(x=>`${x.ts}  ${x.action}  ${x.details}`).join('\n') || 'No recorded events.';});
setInterval(async()=>{if(!S.session||document.hidden||S.polling)return;S.polling=true;try{await refreshJobs();if(S.view==='graph')await S.graph?.refresh(S.eng);if(S.view==='node')await refreshNode();if(selectedCodex()||($('ai-settings-dialog').open&&$('ai-provider').value==='codex'))await refreshCodexStatus();}catch(e){if(e.status===401)$('terminal-state').textContent='Authentication expired. Reload and sign in again.';}finally{S.polling=false;}},3000);
window.addEventListener('online',()=>toast('Network restored. Reconnect a terminal if needed.'));
window.addEventListener('offline',()=>toast('Browser is offline. Node processes may still be running; input is not queued for replay.'));
S.graph=createInvestigationGraph({api,onJob:async id=>{switchTab('jobs');await refreshJobs();await selectJob(id);},toast});
const petUI=window.DreadFoxUI({api,$,text,toast,openPet:()=>switchTab('pet')});
setInterval(()=>{if(S.session && !document.hidden)petUI.refresh({quiet:true});},60000);
boot();

// The browser receives provider metadata only, never decrypted keys.
S.aiSettings=null;
function currentProvider(){return S.aiSettings?.providers.find(p=>p.id===$('ai-provider').value);}
function showProviderControls(){
  const p=currentProvider(),native=p?.id==='codex';
  $('codex-config').hidden=!native;
  const endpoints=p?.endpoints||[];
  $('ai-endpoint').replaceChildren(...endpoints.map(e=>option(e.id,e.label)));
  if(endpoints.length){const old=S.aiSettings.selected;$('ai-endpoint').value=old.provider===p.id&&endpoints.some(e=>e.id===old.endpoint_id)?old.endpoint_id:endpoints[0].id;}
  const local=Boolean(p&&!p.cloud);
  $('ai-endpoint').hidden=!local;
  $('ai-endpoint').previousElementSibling.hidden=!local;
  $('ai-discover').disabled=!p||(!native&&(p.cloud||!endpoints.length));
  $('ai-key-section').hidden=!p||native||p.id==='ollama';
  $('ai-key-status').textContent=p?.has_key?'Credential configured':'No saved credential';
  $('ai-model-options').replaceChildren(...(p?.examples||[]).map(m=>option(m,m)));
  $('ai-provider-note').textContent=!p?'Select a provider to see its requirements.':native?'Sign in with ChatGPT. Use default for Codex’s default model, discover models, or enter an exact model ID. Works with all three assistance modes.':(p.cloud?'Cloud provider · API key required.':'Local/self-hosted · approved endpoint required.')+' Tool calling: '+p.tool_support;
  if(native)refreshCodexStatus().catch(e=>{$('codex-status').textContent=e.message;});
}
function applyAIReadiness(status){
  S.aiSettings=status;
  const operational=status.ready&&status.engine_installed,sel=status.selected,native=sel.provider==='codex';
  $('ai-badge').textContent=operational?'Ready':native?(status.engine_installed?'Sign in':'Install Codex'):(status.ready?'Install engine':'Not configured');
  $('ai-setup-note').hidden=operational;
  $('ai-setup-note').textContent=native?(status.engine_installed?'Sign in with ChatGPT using Provider & model to use the selected Codex model.':'Install the official Codex CLI and add its executable directory to FOXWORX’s tool path.'):(status.ready&&!status.engine_installed?'Install the AI engine on this node to use the selected model.':'Choose a provider and model using Provider & model. Cloud providers use API keys; Codex uses ChatGPT sign-in.');
  if(status.provider_error)$('ai-setup-note').textContent=status.provider_error;
  if(S.session)S.session.ai_configured=operational;
  $('ai-selection-label').textContent=sel.provider&&sel.model?`${status.providers.find(p=>p.id===sel.provider)?.label||sel.provider} · ${sel.model}`:'No model selected · configure AI';
  syncRabbitSubmit();
}
async function refreshAISettings(preserveDraft=false){
  const draft=preserveDraft?{provider:$('ai-provider').value,model:$('ai-model').value,endpoint:$('ai-endpoint').value}:null;
  const status=await api('/api/ai/settings');applyAIReadiness(status);
  const sel=status.selected;
  $('ai-provider').replaceChildren(option('','Choose provider'),...status.providers.map(p=>option(p.id,p.label)));
  if(sel.provider){$('ai-provider').value=sel.provider;showProviderControls();$('ai-model').value=sel.model;}
  else {$('ai-provider').value='';$('ai-model').value='';showProviderControls();}
  if(draft && status.providers.some(p=>p.id===draft.provider)){
    $('ai-provider').value=draft.provider;showProviderControls();
    $('ai-model').value=draft.model;
    if([...$('ai-endpoint').options].some(o=>o.value===draft.endpoint))$('ai-endpoint').value=draft.endpoint;
  }
  return status;
}
$('ai-settings-open').onclick=handle(async()=>{$('ai-key').value='';await refreshAISettings();$('ai-settings-error').textContent='';$('ai-settings-result').textContent='';openDialog('ai-settings-dialog');});
$('ai-settings-dialog').addEventListener('close',()=>{$('ai-key').value='';});
$('ai-provider').onchange=()=>{$('ai-model').value=$('ai-provider').value==='codex'?'default':'';$('ai-key').value='';showProviderControls();};
const aiAction=fn=>async event=>{try{$('ai-settings-error').textContent='';await fn(event);}catch(exc){$('ai-settings-error').textContent=exc.message;}};
$('ai-settings-form').onsubmit=aiAction(async e=>{e.preventDefault();$('ai-settings-error').textContent='';
  const p=currentProvider();if(!p)throw new Error('Choose an AI provider.');
  const data={provider:p.id,model:$('ai-model').value.trim(),endpoint_id:p.cloud?'':$('ai-endpoint').value};
  await api('/api/ai/settings','PUT',data);await refreshAISettings();$('ai-settings-result').textContent='Model selected. Existing chats from other models will not be sent automatically.';
  toast('AI model saved for your operator account.');
});
$('ai-save-key').onclick=aiAction(async()=>{
  const p=currentProvider();if(!p)throw new Error('Choose a provider first.');
  const key=$('ai-key').value.trim();if(!key)throw new Error('Enter an API key to save.');
  await api('/api/ai/keys/'+encodeURIComponent(p.id),'PUT',{api_key:key});$('ai-key').value='';
  await refreshAISettings(true);$('ai-settings-result').textContent='Credential saved encrypted on this node. It will not be shown again.';
});
$('ai-clear-key').onclick=aiAction(async()=>{
  const p=currentProvider();if(!p)throw new Error('Choose a provider first.');
  if(!confirm(`Clear the saved ${p.label} credential for your account? A Pi-level key, if configured, will still be available.`))return;
  await api('/api/ai/keys/'+encodeURIComponent(p.id),'DELETE',{});$('ai-key').value='';await refreshAISettings(true);
  $('ai-settings-result').textContent='Your saved credential was cleared.';
});
$('ai-discover').onclick=aiAction(async()=>{
  const p=currentProvider();if(!p||(p.cloud&&p.id!=='codex'))return;
  $('ai-settings-result').textContent='Discovering available model IDs…';
  const result=await api('/api/ai/models?provider='+encodeURIComponent(p.id)+'&endpoint_id='+encodeURIComponent($('ai-endpoint').value));
  $('ai-model-options').replaceChildren(...result.models.map(m=>option(m,m)));
  $('ai-settings-result').textContent=`${result.models.length} models discovered. Enter or select the exact model ID.`;
});
$('ai-test-connection').onclick=aiAction(async()=>{
  if(!S.aiSettings?.ready)throw new Error('Save the model selection and required credential before testing.');
  const selected=S.aiSettings.selected;
  if(selected.provider!==$('ai-provider').value || selected.model!==$('ai-model').value.trim() || selected.endpoint_id!==($('ai-endpoint').hidden?'':$('ai-endpoint').value))
    throw new Error('Save the displayed model and endpoint before testing; only saved settings can be tested.');
  const btn=$('ai-test-connection');btn.disabled=true;$('ai-settings-result').textContent='Testing saved provider and model…';
  try{const r=await api('/api/ai/test','POST',{});$('ai-settings-result').textContent=`Connected to ${r.provider} / ${r.model}: ${r.reply||'(empty reply)'}. Tool calling remains model-dependent.`;}
  finally{btn.disabled=false;}
});


// Shared findings are untrusted channel data. DOM insertion uses textContent only.
function teamCard(title,detail,subtitle=''){
  const card=text('div','','team-card');card.append(text('strong',title));
  if(subtitle)card.append(text('small',subtitle));
  card.append(text('p',detail,'team-body'));
  return card;
}
async function refreshTeam(){
  if(!S.session||!S.eng||S.teamLoading)return;
  S.teamLoading=true;
  try{
    const eid=S.eng;
    const [response,drafts,runs]=await Promise.all([
      api('/api/discord/messages?engagement_id='+encodeURIComponent(eid)),
      api('/api/discord/drafts?engagement_id='+encodeURIComponent(eid)).catch(()=>[]),
      api('/api/rabbit-runs?engagement_id='+encodeURIComponent(eid)).catch(()=>[])]);
    if(S.eng!==eid)return;
    const stat=response.status;
    $('team-status').textContent=!stat.configured?'Discord is not configured on this node. Ask the node administrator to set the bot token, channel ID and permissions.':
      `Connected to configured channel ${stat.channel_id} · background sync ${stat.poll_seconds}s · ${stat.last_poll?'Last sync '+new Date(stat.last_poll*1000).toLocaleTimeString():'Waiting for first sync'}${stat.last_error?' · '+stat.last_error:''}`;
    const key=response.team_key||'';
    $('team-key-label').textContent=key || 'Not assigned';
    $('team-draft-save').disabled=!stat.configured||!key;
    $('team-rabbit-draft').disabled=!stat.configured||!key;
    $('team-messages').replaceChildren();
    for(const msg of response.messages){
      const box=teamCard(msg.author,msg.content,`${msg.author_bot?'Bot':'Member'} · ${msg.timestamp||'Time unknown'} · UNVERIFIED`);
      if(msg.url){const link=text('a','Open in Discord ↗');link.href=msg.url;link.rel='noopener noreferrer';link.target='_blank';box.append(link);}
      $('team-messages').append(box);
    }
    if(!response.messages.length)$('team-messages').append(text('p',stat.configured?key?'No matching posts yet. Sync or publish your first approved finding.':'Set a team key to connect this engagement.':'Configure Discord to begin.','hint'));
    $('team-drafts').replaceChildren();
    for(const draft of drafts){
      const card=teamCard(`${draft.title} · ${draft.status}`,draft.finding,`${draft.source} · ${draft.team_key}`);
      if(draft.status==='awaiting-approval'){
        const row=text('div','','team-review');const yes=text('button','Approve & publish');const no=text('button','Reject');
        yes.className='primary';no.className='danger-quiet';
        yes.onclick=handle(async()=>{if(!confirm('Publish this exact summary to the configured Discord channel? Everyone with channel access can read it.'))return;yes.disabled=true;no.disabled=true;try{await api('/api/discord/drafts/'+encodeURIComponent(draft.id)+'/review','POST',{engagement_id:eid,approved:true});toast('Discord confirmed the message was published.');}finally{await refreshTeam();}});
        no.onclick=handle(async()=>{await api('/api/discord/drafts/'+encodeURIComponent(draft.id)+'/review','POST',{engagement_id:eid,approved:false});await refreshTeam();});
        row.append(yes,no);card.append(row);
      }
      $('team-drafts').append(card);
    }
    if(!drafts.length)$('team-drafts').append(text('p','No drafts. Save a summary or generate one from a completed Rabbit Hole run.','hint'));
    $('team-rabbit-run').replaceChildren(option('','Choose a finished run'));
    for(const run of (Array.isArray(runs)?runs:[])){
      if(!['queued','running'].includes(run.status))$('team-rabbit-run').append(option(run.id,`${run.status} · ${run.objective?.slice(0,55)||run.id.slice(0,8)}`));
    }
  }finally{S.teamLoading=false;}
}
$('team-refresh').onclick=handle(async()=>{await api('/api/discord/sync','POST',{});await refreshTeam();});
$('team-edit-engagement').onclick=()=>editEngagement(currentEng());
$('team-draft-form').onsubmit=handle(async e=>{e.preventDefault();await api('/api/discord/drafts','POST',{engagement_id:S.eng,title:$('team-draft-title').value.trim(),finding:$('team-draft-content').value.trim()});$('team-draft-form').reset();await refreshTeam();toast('Draft saved locally for explicit approval.');});
$('team-rabbit-draft').onclick=handle(async()=>{const id=$('team-rabbit-run').value;if(!id)return toast('Choose a completed Rabbit Hole run.');await api('/api/discord/drafts/from-rabbit','POST',{engagement_id:S.eng,run_id:id});await refreshTeam();toast('Agent summary drafted; review before publishing.');});
setInterval(()=>{if(S.session&&S.view==='team'&&!document.hidden)refreshTeam().catch(()=>{});},12000);
