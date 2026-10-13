/* DreadFox sanctuary: local pet game + explicit opt-in dialogue.
   Only a separately enabled coarse seven-day workbench pulse is available. */
(function () {
  'use strict';
  const ns = 'http://www.w3.org/2000/svg';
  const categories = [
    ['exploration', '✦', 'Exploration'],
    ['craft', '⚒', 'Craft'],
    ['wisdom', '✧', 'Wisdom'],
    ['stewardship', '◇', 'Careful practice']
  ];
  function svg(name, attrs) {
    const element = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }
  function drawTails(count, target) {
    target.replaceChildren();
    const n = Math.min(9, Math.max(1, count));
    for (let i = 0; i < n; i++) {
      // Fan out behind the fox, with larger, curved, glowing tails as it ages.
      const angle = n === 1 ? 1.0 : (-1.26 + i * (2.52 / (n-1)));
      const tipx = 195 + Math.sin(angle) * 156;
      const tipy = 163 - Math.cos(angle) * 149;
      const bulgex = 195 + Math.sin(angle) * 118;
      const bulgey = 157 - Math.cos(angle) * 112;
      const offset = 13;
      const d = `M 187 234 Q ${bulgex-22} ${bulgey+48} ${tipx} ${tipy}` +
        ` Q ${bulgex+offset+28} ${bulgey+56} 208 235 Z`;
      const group = svg('g', {'class':'spirit-tail', 'style':`--tail-order:${i};`});
      group.append(svg('path', {'d':d, 'fill':'url(#tail-paint)', 'stroke':'#8d4c64', 'stroke-width':'2.3'}));
      group.append(svg('circle', {'cx':tipx, 'cy':tipy, 'r':4+(n>=6?1:0), 'fill':'#ffeac0', 'opacity':'.85'}));
      target.append(group);
    }
  }
  function formatSeconds(seconds) {
    if (!seconds) return '';
    if (seconds >= 3600) return Math.ceil(seconds/3600)+'h';
    return Math.ceil(seconds/60)+'m';
  }
  function percent(value) { return Math.max(0, Math.min(100, Number(value)||0)); }
  window.DreadFoxUI = function ({api, $, text, toast, openPet}) {
    let data = null;
    let busy = false;
    let request = null;
    const el = name => $('pet-'+name);
    const set = (name,value) => { el(name).textContent=String(value); };
    function render(model) {
      data = model;
      el('unavailable').hidden = true;
      el('header-button').hidden = false;
      el('unhatched').hidden = !!model.hatched;
      el('hatched').hidden = !model.hatched;
      if (!model.hatched) {
        set('header-name','Meet DreadFox');set('header-state','A fox spirit awaits');
        return;
      }
      set('header-name',model.name); set('header-state',`${model.stage} · Lv ${model.level}`);
      set('name',model.name);set('stage',model.stage);
      set('level',`Level ${model.level}`);set('tail-count',`${model.tails} of 9 tails`);
      set('xp-label',`${model.xp} / ${model.xp_next} XP`);
      el('xp-progress').style.width=percent((model.xp-model.xp_level_start)/(model.xp_next-model.xp_level_start)*100)+'%';
      for (const key of ['energy','bond','curiosity']) {set(key,model[key]);el(key+'-bar').style.width=percent(model[key])+'%';}
      set('mood-bubble',`${model.mood} · ${model.mood==='Dreaming'?'☾':'✧'}`);
      el('scene').dataset.mood=model.mood.toLowerCase();
      el('portrait').setAttribute('aria-label',`${model.name}, a ${model.mood.toLowerCase()} fox spirit with ${model.tails} tail${model.tails===1?'':'s'}`);
      drawTails(model.tails,$('fox-tails'));
      set('next-tail',model.next_tail?`Next tail: ${model.next_tail.xp} XP and ${model.next_tail.days} days of companionship.`:'All nine tails awakened. Your story continues.');
      set('quote',model.tracking?`Day ${model.age_days} together · ${model.today_xp}/${model.daily_cap} daily XP earned`:'Growth paused · memories preserved');
      el('tracking').checked=!!model.tracking;
      if (document.activeElement!==el('rename')) el('rename').value=model.name;
      for (const type of ['play','feed','rest']) {
        const button=el(type), remaining=model.next_care[type];
        button.disabled=busy||remaining>0;
        const labels={play:'✦ Play', feed:'🍡 Snack', rest:'☾ Rest'};
        button.textContent=labels[type]+(remaining?' · '+formatSeconds(remaining):'');
        button.title=remaining?`Available in ${formatSeconds(remaining)}`:'Spend a moment together';
      }
      const log=el('memories');log.replaceChildren();
      for (const memory of model.memories) {
        const row=text('div','','pet-memory');
        row.append(text('span',memory.kind==='care'?'♥':memory.kind==='hatch'?'✦':'✧','pet-memory-icon'));
        const copy=text('div','','pet-memory-copy');
        const when=new Date(memory.at).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
        copy.append(text('strong',memory.note),text('small',when+(memory.xp?' · +'+memory.xp+' XP':'')));
        row.append(copy);log.append(row);
      }
      if (!model.memories.length) log.append(text('p','New memories will appear here.','hint'));
      const activity=el('activity'); activity.replaceChildren();
      for (const [kind, icon, label] of categories) {
        const row=text('div','','pet-activity-row');
        row.append(text('span',icon,'pet-activity-icon'),text('span',label),text('strong',model.activity[kind]||0));activity.append(row);
      }
      const badges=el('badges');badges.replaceChildren();
      for (const badge of model.badges) {
        const item=text('div','','pet-badge');item.title=badge.detail;
        item.append(text('span',badge.icon),text('small',badge.name));badges.append(item);
      }
      if (!model.badges.length) badges.append(text('p','Your first keepsake is one good session away.','hint'));
      set('age',`Day ${model.age_days} · ${model.xp} lifetime XP`);
      set('streak',model.streak_days+' DAY STREAK');
    }
    async function refresh({quiet=false}={}) {
      if (request) return request;
      request=api('/api/pet');
      try { render(await request); }
      catch (error) { el('unavailable').hidden = false; el('unavailable').textContent = 'Companion temporarily unavailable: '+error.message; if(!quiet)toast('Companion temporarily unavailable: '+error.message); }
      finally { request=null; }
    }
    async function mutate(path,method,body) {
      if (busy) return;
      busy=true;
      try {
        const updated=await api(path,method,body);
        if (updated.hatched!==undefined)render(updated);
        else await refresh();
        if (updated.hatched !== undefined) {await refreshChat({quiet:true});await refreshContext({quiet:true});}
      } catch(error) { toast(error.message);await refresh({quiet:true}); }
      finally { busy=false; if(data)render(data); }
    }
    // Coarse Workbench Pulse: no raw operational details are requested.
    // The server derives these bands from a strict built-in event allowlist.
    let contextBusy = false;
    const pulseLabels = {
      completed_jobs:'Completed jobs', unfinished_jobs:'Unfinished jobs',
      reviewed_jobs:'Reviewed operations', terminal_sessions:'Terminal sessions',
      learning_sessions:'AI learning', workspace_planning:'Workspace planning',
      evidence_organization:'Evidence organization'
    };
    const pulseLevels = {some:'Some',a_few:'A few',several:'Several',frequent:'Frequent'};
    function renderContext(context) {
      el('context-enable').checked=!!context.enabled;
      el('pulse-state').textContent=!context.enabled?'Off · private':(!context.tracking?'Paused with pet':'On · seven-day pulse');
      el('context-clear').disabled=contextBusy||!context.enabled;
      const preview=el('context-preview');preview.replaceChildren();
      if(!context.enabled) {
        preview.append(text('span','No operations data is shared with DreadFox.','hint'));
      } else if(!context.tracking) {
        preview.append(text('span','Pet activity tracking is paused; no pulse is shared.','hint'));
      } else if(!context.signals?.length) {
        preview.append(text('span','No eligible activity yet. Existing work is never backfilled.','hint'));
      } else {
        for(const signal of context.signals) {
          const label=pulseLabels[signal.area];
          if(label) preview.append(text('span',`${pulseLevels[signal.level] || 'Some'} · ${label}`,'pulse-signal'));
        }
      }
    }
    async function refreshContext({quiet=false}={}) {
      if(!data?.hatched) return;
      try {renderContext(await api('/api/pet/context'));}
      catch(error) {if(!quiet)toast('Workbench Pulse unavailable: '+error.message);}
    }
    el('context-enable').addEventListener('change',async()=>{
      if(contextBusy) return;
      const enabled=el('context-enable').checked;
      if(enabled&&!confirm('Enable Workbench Pulse? DreadFox will retain only broad activity categories and approximate frequency for up to seven days. If AI chat is also on, that summary will be sent to your selected model provider. No past activity is imported.')) {
        el('context-enable').checked=false;return;
      }
      contextBusy=true;
      try {renderContext(await api('/api/pet/context','PUT',{enabled}));toast(enabled?'Workbench Pulse enabled.':'Workbench Pulse erased and disabled.');}
      catch(error) {toast(error.message);await refreshContext({quiet:true});}
      finally {contextBusy=false;await refreshContext({quiet:true});}
    });
    el('context-clear').addEventListener('click',async()=>{
      if(contextBusy||!confirm('Turn off and erase the seven-day operations pulse? This will not delete existing DreadFox chat history or undo earlier model requests.'))return;
      contextBusy=true;
      try {renderContext(await api('/api/pet/context','DELETE',{}));toast('Workbench Pulse erased.');}
      catch(error) {toast(error.message);await refreshContext({quiet:true});}
      finally {contextBusy=false;await refreshContext({quiet:true});}
    });
    // Companion dialogue stays separate. Never forward actual terminal text,
    // job records, evidence, target names, or copilot history to pet chat.
    let chatBusy = false;
    let chatMode = 'offline';
    function renderChat(history) {
      if (!history.hatched) return;
      chatMode = history.mode;
      el('chat-ai').checked = history.mode === 'ai';
      el('chat-focus').value = history.focus || 'auto';
      el('chat-mode-label').textContent = history.mode === 'ai' ? 'Selected AI · opt-in' : 'Offline · no AI calls';
      el('chat-personality').textContent = `${history.personality.title} · ${history.personality.description} (${history.personality.source})`;
      const log = el('chat-messages'); log.replaceChildren();
      if (!history.messages.length) log.append(text('p','Say hello to your fox. Ask about its mood, tails or memories.','hint'));
      for (const message of history.messages) {
        const bubble = text('div','','pet-chat-bubble ' + (message.role === 'user' ? 'from-user' : 'from-fox'));
        const name = message.role === 'user' ? 'You' : (data?.name || 'DreadFox');
        bubble.append(text('strong', name, 'pet-chat-speaker'), text('p', message.text));
        if (message.role === 'assistant') bubble.append(text('small',message.mode === 'ai' ? `✧ ${message.provider} / ${message.model}` : '✦ Offline response','pet-chat-source'));
        log.append(bubble);
      }
      log.scrollTop = log.scrollHeight;
    }
    async function refreshChat({quiet=false}={}) {
      if (!data?.hatched) return;
      try {renderChat(await api('/api/pet/chat'));}
      catch(error) {el('chat-status').textContent='Conversation unavailable: '+error.message; if (!quiet)toast(error.message);}
    }
    async function changeChat(path, method, value) {
      if (chatBusy) return;
      chatBusy=true;
      try {renderChat(await api(path,method,value)); el('chat-status').textContent='Companion preferences saved.';}
      catch(error) {toast(error.message); await refreshChat({quiet:true});}
      finally {chatBusy=false;}
    }
    el('chat-ai').addEventListener('change', async () => {
      const enabled=el('chat-ai').checked;
      if (enabled && !confirm('AI DreadFox chats can incur model costs and send your typed messages to the chosen provider. Existing DreadFox chats are only forwarded to the same provider and model. Enable?')) {
        el('chat-ai').checked=false;return;
      }
      await changeChat('/api/pet/chat/mode','PUT',{mode:enabled?'ai':'offline'});
    });
    el('chat-focus').addEventListener('change',()=>changeChat('/api/pet/chat/focus','PUT',{focus:el('chat-focus').value}));
    el('chat-form').addEventListener('submit', async event => {
      event.preventDefault(); if (chatBusy) return;
      const value=el('chat-input').value.trim(); if (!value) return;
      chatBusy=true;el('chat-send').disabled=true;
      el('chat-status').textContent=chatMode==='ai'?'Your chosen model is responding…':'Your fox is listening…';
      try {
        const response=await api('/api/pet/chat','POST',{message:value});
        el('chat-input').value='';
        await refreshChat({quiet:true});
        el('chat-status').textContent=response.mode==='ai'?`Reply from ${response.provider} / ${response.model}`:'Offline companion response · no model request';
      } catch(error) {el('chat-status').textContent=error.message+' Your draft was preserved.';toast(error.message);}
      finally {chatBusy=false;el('chat-send').disabled=false;}
    });
    el('chat-input').addEventListener('keydown', event => {if(event.ctrlKey&&event.key==='Enter'){event.preventDefault();el('chat-form').requestSubmit();}});
    el('chat-clear').addEventListener('click',async()=>{
      if (!confirm('Clear all saved DreadFox conversations? Your fox, tails, XP and journal will remain.'))return;
      await changeChat('/api/pet/chat','DELETE',{});
    });
    el('header-button').addEventListener('click',()=>{openPet();refreshChat({quiet:true});refreshContext({quiet:true});});
    el('refresh').addEventListener('click',async()=>{await refresh();await refreshChat();await refreshContext();});
    el('hatch').addEventListener('click',()=>mutate('/api/pet/hatch','POST',{}));
    el('rename-save').addEventListener('click',()=>mutate('/api/pet/name','PUT',{name:el('rename').value}));
    el('rename').addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();el('rename-save').click();}});
    for (const action of ['play','feed','rest']) {
      el(action).addEventListener('click',()=>mutate('/api/pet/care','POST',{action}));
    }
    el('tracking').addEventListener('change',()=>mutate('/api/pet/tracking','PUT',{enabled:el('tracking').checked}));
    el('delete').addEventListener('click',async()=>{
      if(!confirm('Erase DreadFox permanently? This deletes all pet XP, tails, milestones, and journal entries. Your workbench, evidence and AI history stay untouched.'))return;
      await mutate('/api/pet','DELETE',{});toast('Companion data erased. The rest of FOXWORX is unchanged.');
    });
    el('reset').addEventListener('click',async()=>{
      if(!confirm('Start DreadFox over from the beginning? All current pet memories and XP will be erased.'))return;
      if(busy)return;
      busy=true;
      try { await api('/api/pet','DELETE',{});render(await api('/api/pet/hatch','POST',{}));await refreshChat({quiet:true});await refreshContext({quiet:true});toast('A new fox spirit has hatched.'); }
      catch(error){toast(error.message);await refresh({quiet:true});}
      finally {busy=false;if(data)render(data);}
    });
    return {refresh,refreshChat,refreshContext};
  };
})();
