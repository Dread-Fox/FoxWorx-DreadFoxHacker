/* FOXWORX v3.0 — investigation graph. Entirely local, read-only viewer.
   Source of truth is the authenticated, engagement-scoped graph API.
   Draws a scalable SVG; no third-party scripts or network CDNs. */
const NS='http://www.w3.org/2000/svg';
const $=id=>document.getElementById(id);
const svg=(tag,attributes={})=>{const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attributes))el.setAttribute(k,String(v));return el;};
const text=(tag,value,cls='')=>{const el=document.createElement(tag);el.textContent=value;if(cls)el.className=cls;return el;};
const trim=(v,n=42)=>String(v||'').length>n?String(v).slice(0,n-1)+'…':String(v||'');
const palette={engagement:'#ffb66d',run:'#b69bfd',job:'#6cd5b0',step:'#f5af6d',observation:'#7eb6f5',asset:'#e6b86b'};
const statuses={succeeded:'#6dd4ad',solved:'#6dd4ad',running:'#ffc078',queued:'#ffc078',failed:'#f88798',blocked:'#f88798',stopped:'#a6b4ca',observed:'#7eb6f5'};
const nodeDims={w:202,h:71};
function download(name,data,type){const blob=new Blob([data],{type});const url=URL.createObjectURL(blob);try{const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();}finally{setTimeout(()=>URL.revokeObjectURL(url),4000);}}

export function createInvestigationGraph({api,onJob,toast}){
  let data=null,selected='',projection=[],edges=[],view='execution',scale=.82,x=25,y=38,refreshing=false;
  let lastEng='',drag=null,positions=new Map();
  const canvas=$('graph-canvas'),world=svg('g',{'id':'graph-world'});
  const viewportWidth=()=>window.innerWidth<=650?500:1200;
  const resizeViewport=()=>canvas.setAttribute('viewBox',`0 0 ${viewportWidth()} 620`);
  canvas.append(world);
  const name=()=>`foxworx-graph-${lastEng?.slice(0,8)||'engagement'}`;
  function mode(){return $('graph-mode').value;}
  function filtered(){
    if(!data)return {nodes:[],edges:[]};
    const query=$('graph-filter').value.toLowerCase().trim(),status=$('graph-status').value;
    const days=Number($('graph-days').value),dateCut=days>0?Date.now()-days*86400000:0;
    const candidates=data.nodes.filter(n=>{
      if(mode()==='execution'&&['observation','asset'].includes(n.kind))return false;
      if(mode()==='investigation'&&n.kind==='step')return false;
      if(query&&!`${n.label} ${n.tool||''} ${n.origin||''} ${n.status||''}`.toLowerCase().includes(query))return false;
      if(status&&n.status!==status)return false;
      if(dateCut&&n.kind!=='engagement'&&n.created&&Date.parse(n.created)<dateCut)return false;
      return true;
    });
    // Keep a bounded render even if a node has hundreds of recorded jobs.
    const root=data.nodes.find(n=>n.kind==='engagement');
    const visible=candidates.filter(n=>n.kind!=='engagement').slice(-65);
    if(root&&(!query&&!status||candidates.includes(root)))visible.unshift(root);
    const ids=new Set(visible.map(n=>n.id));
    return {nodes:visible,edges:data.edges.filter(e=>ids.has(e.source)&&ids.has(e.target))};
  }
  function transform(){world.setAttribute('transform',`translate(${x} ${y}) scale(${scale})`);$('graph-zoom-label').textContent=Math.round(scale*100)+'%';}
  function setScale(next){const old=scale;scale=Math.min(2.4,Math.max(.28,next));x=viewportWidth()/2-(viewportWidth()/2-x)*scale/old;y=280-(280-y)*scale/old;transform();}
  function layout(nodes){
    const lanes=new Map([['engagement',[]],['run',[]],['asset',[]],['job',[]],['step',[]],['observation',[]]]);
    for(const n of nodes)lanes.get(n.kind)?.push(n);
    const maxItems=Math.max(1,...[...lanes.values()].map(arr=>arr.length));
    positions=new Map();
    const ordered=[...lanes.get('engagement'),...lanes.get('run'),...lanes.get('asset'),...lanes.get('step'),...lanes.get('job'),...lanes.get('observation')];
    const depths={engagement:0,run:1,asset:1,step:2,job:2,observation:3};
    // Four fixed columns remain legible as the graph expands vertically.
    const groupCounts={};for(const n of ordered){let d=depths[n.kind];let idx=groupCounts[d]||0;groupCounts[d]=idx+1;positions.set(n.id,{x:d*261+25,y:idx*97+42});}
    return Math.max(600,maxItems*97+120);
  }
  function render(){
    if(!data)return;
    resizeViewport();
    const choice=filtered();projection=choice.nodes;edges=choice.edges;
    $('graph-total').textContent=`${data.nodes.filter(n=>n.kind==='job').length} jobs · ${data.nodes.filter(n=>n.kind==='run').length} runs · ${data.nodes.filter(n=>n.kind==='observation').length} parsed observations`;
    $('graph-visible').textContent=`${projection.length} shown${data.truncated?' · history capped':''} · ${edges.length} links`;
    const height=layout(projection);world.replaceChildren();
    const defs=svg('defs'),marker=svg('marker',{id:'fox-graph-arrow',markerWidth:9,markerHeight:9,refX:7,refY:4,orient:'auto'});
    marker.append(svg('path',{d:'M0 0 L8 4 L0 8 Z',fill:'#6c829e'}));defs.append(marker);world.append(defs);
    for(const edge of edges){
      const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)continue;
      const startX=a.x+nodeDims.w,startY=a.y+nodeDims.h/2,endX=b.x,endY=b.y+nodeDims.h/2;
      const dx=Math.max(28,(endX-startX)*.52);
      const d=`M ${startX} ${startY} C ${startX+dx} ${startY} ${endX-dx} ${endY} ${endX} ${endY}`;
      const path=svg('path',{d,fill:'none',stroke:edge.kind==='retry'?'#ef9b67':'#617d9a',
        'stroke-width':edge.kind==='retry'?2.6:1.7,'stroke-opacity':'.78', 'marker-end':'url(#fox-graph-arrow)'});
      const title=svg('title');title.textContent=edge.label||edge.kind;path.append(title);
      world.append(path);
    }
    for(const node of projection){
      const pos=positions.get(node.id),g=svg('g',{transform:`translate(${pos.x} ${pos.y})`,
        tabindex:0,role:'button','aria-label':`${node.kind}: ${node.label}, ${node.status}`,
        'class':'fox-graph-node'+(node.id===selected?' picked':'')});
      const color=statuses[node.status]||palette[node.kind]||'#98a9ba';
      g.append(svg('rect',{width:nodeDims.w,height:nodeDims.h,rx:11,fill:'#1b2636',stroke:node.id===selected?'#ffe1a6':color,'stroke-width':node.id===selected?2.5:1.4}));
      g.append(svg('rect',{width:4,height:nodeDims.h,rx:2,fill:color}));
      const kind=svg('text',{x:15,y:19,fill:'#a6b8d1','font-size':11,'font-family':'system-ui, sans-serif'});
      kind.textContent=({engagement:'ENGAGEMENT',run:'RABBIT HOLE',asset:'APPROVED TARGET',job:'TOOL JOB',step:'AGENT STEP',observation:'PARSED OUTPUT'})[node.kind];g.append(kind);
      const label=svg('text',{x:15,y:42,fill:'#f2f5ff','font-weight':650,'font-size':14,'font-family':'system-ui, sans-serif'});
      label.textContent=trim(node.label,24);g.append(label);
      const state=svg('text',{x:15,y:59,fill:color,'font-size':10,'font-family':'system-ui, sans-serif'});
      state.textContent=trim(`${node.status||''} · ${node.tool||node.origin||''}`,32);g.append(state);
      g.addEventListener('click',()=>choose(node.id));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(node.id);}});
      world.append(g);
    }
    $('graph-empty').hidden=projection.length>1;
    const list=$('graph-node-list');list.replaceChildren();
    for(const node of projection){
      if(node.kind==='engagement')continue;
      const b=text('button',`${node.kind==='observation'?'◇':node.kind==='run'?'◈':'⬢'} ${trim(node.label,38)} · ${node.status}`,'graph-list-item');
      b.type='button';b.classList.toggle('active',node.id===selected);b.onclick=()=>choose(node.id);list.append(b);
    }
    if(selected&&!projection.some(n=>n.id===selected))selected='';
    inspector();transform();
  }
  function choose(id){selected=id;render();}
  function inspector(){
    const target=$('graph-inspector'),node=data?.nodes.find(n=>n.id===selected);
    target.replaceChildren();
    if(!node){target.append(text('p','Select a graph node to inspect its recorded status, provenance, evidence and annotations.','hint'));return;}
    target.append(text('h3',node.label),text('p',`${node.kind.toUpperCase()}  ·  ${node.status}  ·  ${node.origin||'local'}`,'graph-subtitle'));
    const fields=[['Recorded',node.created],['Tool',node.tool],['Exit code',node.returncode],['Ended',node.ended],['Confidence',node.confidence],['Source',node.description],['Evidence',node.evidence]];
    const dl=text('dl','','graph-metadata');for(const [k,v] of fields){if(v===undefined||v===null||v==='')continue;dl.append(text('dt',k),text('dd',String(v)));}target.append(dl);
    if(node.kind==='observation')target.append(text('p','Parsed output is NOT a verified security finding. Confirm independently before reporting.','graph-warning'));
    if(node.job_id||node.evidence_job_id){const button=text('button','Open recorded job & output','primary');button.onclick=()=>onJob(node.job_id||node.evidence_job_id);target.append(button);}
    if(node.run_id){const runbutton=text('button','Show Rabbit Hole run');runbutton.onclick=()=>toast('Select Rabbit Hole in the AI sidebar for the live run and conclusion.');target.append(runbutton);}
    const label=text('label','Private annotation (saved on this node)');label.htmlFor='graph-note-text';target.append(label);
    const textarea=document.createElement('textarea');textarea.id='graph-note-text';textarea.maxLength=1200;textarea.rows=3;textarea.value=node.note||'';textarea.placeholder='Record a verified interpretation or follow-up action…';target.append(textarea);
    const save=text('button','Save annotation');save.onclick=async()=>{save.disabled=true;try{const v=await api(`/api/engagements/${encodeURIComponent(lastEng)}/graph/notes`,'PUT',{node_id:node.id,note:textarea.value});node.note=v.note;toast('Annotation saved.');}catch(e){toast(e.message);}finally{save.disabled=false;}};target.append(save);
  }
  async function refresh(eng){
    if(!eng||refreshing)return;
    refreshing=true;try{const response=await api(`/api/engagements/${encodeURIComponent(eng)}/graph`);if(eng!==lastEng)return;data=response;render();$('graph-updated').textContent='Updated '+new Date().toLocaleTimeString();}catch(e){$('graph-updated').textContent='Graph unavailable: '+e.message;toast(e.message);}finally{refreshing=false;}
  }
  function setEngagement(eng){lastEng=eng;data=null;selected='';scale=.82;x=25;y=38;world.replaceChildren();$('graph-total').textContent='Loading engagement history…';$('graph-inspector').replaceChildren(text('p','Select an operation on the map.','hint'));}
  for(const id of ['graph-mode','graph-status','graph-days'])$(id).addEventListener('change',render);
  $('graph-filter').addEventListener('input',render);
  $('graph-refresh').addEventListener('click',()=>refresh(lastEng));
  $('graph-zoom-in').addEventListener('click',()=>setScale(scale*1.25));
  $('graph-zoom-out').addEventListener('click',()=>setScale(scale/1.25));
  $('graph-fit').addEventListener('click',()=>{scale=.82;x=25;y=38;transform();});
  canvas.addEventListener('wheel',e=>{e.preventDefault();setScale(scale*(e.deltaY<0?1.13:.885));},{passive:false});
  canvas.addEventListener('pointerdown',e=>{if(e.target.closest('.fox-graph-node'))return;drag={px:e.clientX,py:e.clientY,x,y};canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!drag)return;const r=canvas.getBoundingClientRect();x=drag.x+(e.clientX-drag.px)*viewportWidth()/r.width;y=drag.y+(e.clientY-drag.py)*620/r.height;transform();});
  canvas.addEventListener('pointerup',()=>{drag=null;});canvas.addEventListener('pointercancel',()=>{drag=null;});
  $('graph-export-json').addEventListener('click',()=>{if(data)download(name()+'.json',JSON.stringify({...data,visible_node_ids:projection.map(n=>n.id)},null,2),'application/json');});
  function exportedSVG(){const clone=canvas.cloneNode(true);clone.setAttribute('xmlns',NS);clone.setAttribute('width',String(viewportWidth()));clone.setAttribute('height','620');clone.setAttribute('viewBox',`0 0 ${viewportWidth()} 620`);clone.setAttribute('style','background:#111c2b');return new XMLSerializer().serializeToString(clone);}
  $('graph-export-svg').addEventListener('click',()=>{if(data)download(name()+'.svg',exportedSVG(),'image/svg+xml');});
  $('graph-export-png').addEventListener('click',()=>{if(!data)return;const image=new Image();image.onload=()=>{const c=document.createElement('canvas');c.width=1800;c.height=930;const ctx=c.getContext('2d');ctx.fillStyle='#111c2b';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(image,0,0,c.width,c.height);c.toBlob(b=>{if(b)download(name()+'.png',b,'image/png');else toast('PNG export was unavailable; use SVG.');});};image.onerror=()=>toast('PNG renderer unavailable; use SVG.');image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(exportedSVG());});
  window.addEventListener('resize',()=>{resizeViewport();transform();});
  return {refresh,setEngagement,render};
}
