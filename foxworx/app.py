"""HTTP/WebSocket application; one process/worker owns its sessions and job pool."""
from contextlib import asynccontextmanager
import asyncio
import base64
import json
import logging
import os
from pathlib import Path
import platform
import shutil
import shlex
import time
from urllib.parse import quote, unquote
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from . import __version__
from .config import Settings, ROOT
from .auth import Auth
from .store import Store
from .models import ToolNote, Login, Engagement, ProposalSpec, Approval, SessionSpec, ChatSpec, ArgumentText, AISelection, AIKeyChange, PetName, PetCare, PetTracking, PetChatMessage, PetChatMode, PetChatFocus, PetContextToggle, RabbitSpec, RegisteredProposalSpec
from .registry import Registry, ToolDiscovery
from .models import RabbitMessage
from .tool_intelligence import ToolIntelligence
from .jobs import JobManager, ACTIVE, PROFILES
from .terminal import TerminalManager
from .ai import Copilot
from .rabbit import RabbitRunner
from .operation_graph import InvestigationGraph
from .codex_agent import CodexAgent
from .discord_team import DiscordTeam, clean
from .providers import ProviderManager, PROVIDERS
from .model_gateway import ModelGateway
from .evidence import safe_open, list_files, export_evidence, MAX_UPLOAD
from .platforms import host_snapshot
from .hardware_intelligence import HardwareIntelligence
from .pet import DreadFoxPet
from .pet_chat import DreadFoxConversation


def diagnostics(cfg, registry, jobs, terminals):
    disk = shutil.disk_usage(cfg.state)
    memory = {}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            name, value = line.split(':',1)
            if name in ('MemTotal','MemAvailable'):
                memory[name] = int(value.strip().split()[0])*1024
    except (OSError, ValueError):
        pass
    items = registry.list()
    hardware=host_snapshot()
    return {'version':__version__, 'host':platform.node(), 'architecture':platform.machine(), 'python':platform.python_version(),
            'mode':cfg.mode, 'origin':cfg.origin, 'public_origin':cfg.public_origin, 'uid':os.getuid(), 'free_disk_bytes':disk.free,
            'hardware':hardware,
            'memory':memory, 'load':list(os.getloadavg()), 'active_jobs':len(jobs.tasks),
            'terminal_sessions':len(terminals.sessions), 'max_jobs':cfg.max_jobs, 'max_terminals':cfg.max_terminals,
            'installed_executables':sum(t['installed'] for t in items),
            'curated_installed':sum(t['installed'] and t['curated'] for t in items),
            'curated_total':sum(t['curated'] for t in items),
            'ai_configured':bool(cfg.api_key and cfg.model), 'ai_model':cfg.model,
            'state_directory':str(cfg.state), 'config_file':str(cfg.config_path),
            'limits':{'job_timeout_seconds':cfg.job_timeout, 'job_log_bytes':cfg.log_bytes, 'upload_bytes':MAX_UPLOAD,
                      'detached_terminal_seconds':3600, 'terminal_replay_bytes':262144},
            'warnings':['Trusted operators share this Linux account. Web ownership is not OS isolation.',
                        'The terminal and advanced jobs are not constrained by engagement input checks.',
                        'Token-free mode grants any visitor reachable through your tunnel the Linux service account capabilities.',
                        'Cloudflare Tunnel is browser ingress; it does not proxy tool scan traffic.',
                        'No embedded GUI desktop, GPU sharing/virtualization, or automatic HackerOne authorization.']}


def create_app(cfg: Settings | None = None, *, _allow_root_for_tests: bool = False, ai_transport=None) -> FastAPI:
    cfg = cfg or Settings.load()
    cfg.validate()
    if os.geteuid() == 0 and not _allow_root_for_tests:
        raise RuntimeError('Run FOXWORX as a dedicated non-root Linux user, never root')
    auth, store, registry = Auth(cfg), Store(cfg.state), Registry(cfg)
    jobs, terminals = JobManager(cfg, store, registry), TerminalManager(cfg, store)
    knowledge = ToolIntelligence(cfg,registry)
    discovery = ToolDiscovery(registry,cfg.state)
    codex = CodexAgent(cfg,store,jobs)
    providers = ProviderManager(cfg,store,codex=codex)
    ai = Copilot(cfg, store, registry, jobs, providers=providers, knowledge=knowledge,discovery=discovery,
                 gateway=ModelGateway(codex=codex))
    rabbit = RabbitRunner(cfg,store,jobs,providers,ai.gateway,knowledge=knowledge,discovery=discovery)
    hardware = HardwareIntelligence(store)
    jobs.hardware = hardware
    graph = InvestigationGraph(store,cfg.state)
    discord = DiscordTeam(cfg,store)
    ai.discord = discord
    rabbit.discord = discord
    codex.discord = discord
    try:
        pet = DreadFoxPet(store)
    except Exception:
        # Optional companion corruption must not disable terminal, jobs or AI.
        logging.getLogger(__name__).exception('DreadFox storage unavailable; workbench remains operational')
        pet = None

    try:
        pet_chat = DreadFoxConversation(pet, providers, ai.gateway) if pet is not None else None
    except Exception:
        logging.getLogger(__name__).exception('DreadFox dialogue storage unavailable; core workbench remains operational')
        pet_chat = None

    def conversation():
        if pet_chat is None:
            raise HTTPException(503, 'DreadFox conversation is temporarily unavailable; other operations are unaffected.')
        return pet_chat

    def companion():
        if pet is None:
            raise HTTPException(503, 'DreadFox pet storage is unavailable. The rest of FOXWORX remains operational; review service logs and your state backup.')
        return pet

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(registry.scan)
        await asyncio.to_thread(discovery.rebuild)
        discovery.request_refresh(enrich_only=True)
        jobs.recover()
        rabbit.recover()
        await discord.start()
        if pet is not None: pet.start()
        terminals.reaper = asyncio.create_task(terminals.reap())
        yield
        await discord.shutdown()
        await rabbit.shutdown()
        await codex.shutdown()
        await jobs.shutdown()
        await terminals.shutdown()
        await asyncio.to_thread(discovery.close)
        if pet is not None: await pet.stop()

    app = FastAPI(title='FOXWORX Workbench', version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.cfg, app.state.auth, app.state.store = cfg, auth, store
    app.state.registry, app.state.jobs, app.state.terminals, app.state.ai = registry, jobs, terminals, ai
    app.state.hardware = hardware
    app.state.providers = providers
    app.state.knowledge = knowledge
    app.state.discovery = discovery
    app.state.rabbit = rabbit
    app.state.graph = graph
    app.state.codex = codex
    app.state.discord = discord
    app.state.pet = pet
    app.state.pet_chat = pet_chat

    async def ai_status_for(owner):
        error=''
        if providers.selection(owner)['provider']=='codex':
            try:await codex.status(owner)
            except HTTPException as exc:
                codex.accounts.pop(owner,None)
                error=str(exc.detail)
        status=providers.describe(owner)
        if error:status['provider_error']=error
        return status

    @app.middleware('http')
    async def guard(request: Request, call_next):
        try:
            auth.check_host(request)
            if cfg.mode == 'cloudflare':
                await auth.actor(request)
            if request.method in ('POST','PUT','PATCH','DELETE'):
                raw_length = request.headers.get('content-length')
                if raw_length is None or not raw_length.isdecimal() or 'transfer-encoding' in request.headers:
                    raise HTTPException(411, 'A bounded Content-Length is required')
                limit = MAX_UPLOAD if request.url.path.endswith('/files') else 65536
                if int(raw_length) > limit:
                    raise HTTPException(413, 'Request exceeds the allowed size')
            response = await call_next(request)
        except HTTPException as exc:
            response = JSONResponse({'detail':exc.detail}, status_code=exc.status_code)
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
            'Referrer-Policy':'no-referrer','Cache-Control':'no-store',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            'Permissions-Policy':'camera=(), microphone=(), geolocation=()'})
        return response

    async def actor(request, mutate=False):
        who = await auth.actor(request)
        if mutate: auth.mutation(request, who)
        return who.name

    @app.get('/')
    async def index():
        return FileResponse(ROOT/'static/index.html')

    @app.get('/api/auth-mode')
    async def auth_mode():
        return {'mode':cfg.mode, 'version':__version__, 'public_origin':cfg.public_origin}

    @app.post('/api/login')
    async def login(spec: Login, request: Request):
        if cfg.mode == 'open':
            raise HTTPException(404, 'Login is not required in token-free mode')
        auth.origin(request)
        token = auth.login(spec.token, remember=spec.remember)
        response = JSONResponse({'ok':True})
        response.set_cookie('foxworx_local',token,httponly=True,
                            secure=(cfg.mode == 'proxy' or auth.is_public_host(request)),
                            samesite='lax',max_age=(30 * 86400 if spec.remember else 28800),path='/')
        store.event('local-operator','local-login')
        return response

    @app.post('/api/logout')
    async def logout(request: Request):
        await actor(request,True)
        if cfg.mode == 'open':
            return {'ok':True,'cloudflare_logout':None,'message':'Token-free mode has no login session to end'}
        response = JSONResponse({'ok':True,'cloudflare_logout':'/cdn-cgi/access/logout' if cfg.mode == 'cloudflare' else None})
        response.delete_cookie('foxworx_local',path='/')
        return response

    @app.get('/api/session')
    async def session(request: Request):
        owner = await actor(request)
        if not store.list('engagement',owner):
            store.put('engagement',owner,{'name':'Local lab','include':['127.0.0.1','::1','localhost'],'exclude':[],
                                        'notes':'Local test environment only. Create a separate engagement for each authorized program.', 'program_url':''})
        ai_status=await ai_status_for(owner)
        return {'actor':owner, 'csrf':auth.csrf(owner), **diagnostics(cfg,registry,jobs,terminals),
                'ai_configured':ai_status['ready'],'ai_model':ai_status['selected']['model'],
                'ai_provider':ai_status['selected']['provider']}

    @app.get('/api/diagnostics')
    async def diag(request: Request):
        await actor(request)
        info=diagnostics(cfg,registry,jobs,terminals)
        status=await ai_status_for(await actor(request))
        return {**info,'ai_configured':status['ready'],'ai_model':status['selected']['model'],
                'ai_provider':status['selected']['provider']}

    @app.get('/api/hardware')
    async def hardware_inventory(request: Request, fresh: bool = False):
        owner=await actor(request)
        report=await asyncio.to_thread(hardware.inventory,owner,fresh=fresh)
        nvidia=await asyncio.to_thread(host_snapshot,fresh=fresh)
        return {**report,'nvidia':nvidia['gpus'],'nvidia_status':nvidia['gpu_status']}

    @app.put('/api/hardware/interfaces/{name}/role')
    async def hardware_set_role(name: str, request: Request):
        owner=await actor(request,True)
        payload=await request.json()
        if not isinstance(payload,dict) or set(payload)!={'role'} or not isinstance(payload['role'],str):
            raise HTTPException(422,'Expected role only')
        return await asyncio.to_thread(hardware.assign,owner,name,payload['role'])

    @app.get('/api/discord/status')
    async def discord_status(request: Request):
        await actor(request)
        return discord.status()

    @app.get('/api/discord/messages')
    async def discord_messages(request: Request, engagement_id: str):
        owner=await actor(request)
        eng=jobs.engagement(owner,engagement_id)
        return {'messages':discord.messages(owner,eng), 'team_key':eng.get('team_key',''),
                'status':discord.status()}

    @app.post('/api/discord/sync')
    async def discord_sync(request: Request):
        await actor(request,True)
        return await discord.sync()

    @app.get('/api/discord/drafts')
    async def discord_drafts(request: Request, engagement_id: str):
        return discord.drafts(await actor(request),engagement_id)

    @app.post('/api/discord/drafts')
    async def discord_create_draft(request: Request):
        owner=await actor(request,True)
        body=await request.json()
        if not isinstance(body,dict) or set(body)-{'engagement_id','title','finding','job_id','source'}:
            raise HTTPException(422,'Unexpected draft fields')
        if body.get('source','operator') not in ('operator','agent'):
            raise HTTPException(422,'Invalid source')
        # Agent-authored summaries can be proposed by the operator from a saved
        # run; arbitrary source labels cannot change approval requirements.
        if body.get('source')=='agent':
            raise HTTPException(403,'Agent drafts must originate from a saved agent run')
        return discord.draft(owner,body.get('engagement_id',''),body.get('title',''),
                             body.get('finding',''),job_id=body.get('job_id',''))

    @app.post('/api/discord/drafts/from-rabbit')
    async def discord_draft_rabbit(request: Request):
        owner=await actor(request,True)
        body=await request.json()
        if not isinstance(body,dict) or set(body)!={'run_id','engagement_id'}:
            raise HTTPException(422,'run_id and engagement_id required')
        run=rabbit.get(owner,body['run_id'])
        if run['engagement_id']!=body['engagement_id'] or run['status'] in ('queued','running'):
            raise HTTPException(409,'Only finished agent runs in this engagement may be summarized')
        result=discord.draft(owner,body['engagement_id'],'Rabbit Hole: '+clean(run.get('objective',''),65),
                             run.get('summary','No findings reported'),source='agent')
        return result

    @app.post('/api/discord/drafts/{draft_id}/review')
    async def discord_review_draft(draft_id: str, request: Request):
        owner=await actor(request,True)
        body=await request.json()
        if not isinstance(body,dict) or set(body)!={'engagement_id','approved'} or type(body['approved']) is not bool:
            raise HTTPException(422,'engagement_id and Boolean approved required')
        return await discord.publish(owner,body['engagement_id'],draft_id,body['approved'])

    @app.get('/api/adapter-policy')
    async def adapter_policy_inventory(request: Request):
        await actor(request)
        return rabbit.policy.inventory(registry)

    @app.get('/api/rabbit-runs')
    async def rabbit_list(request: Request, engagement_id: str = ''):
        return rabbit.list(await actor(request),engagement_id=engagement_id)

    @app.post('/api/rabbit-runs')
    async def rabbit_begin(spec: RabbitSpec, request: Request):
        return rabbit.start(await actor(request,True),spec)

    @app.get('/api/rabbit-runs/{id}')
    async def rabbit_get(id: str, request: Request):
        return rabbit.get(await actor(request),id)

    @app.post('/api/rabbit-runs/{id}/stop')
    async def rabbit_cancel(id: str, request: Request):
        return await rabbit.stop(await actor(request,True),id)

    @app.post('/api/rabbit-runs/{id}/messages')
    async def rabbit_message(id: str,spec: RabbitMessage,request: Request):
        return rabbit.add_message(await actor(request,True),id,spec.message)

    # Provider sign-in remains first-party managed. Legacy history endpoints
    # preserve old records without forwarding them into shared chat context.
    @app.get('/api/codex/status')
    async def codex_status(request: Request):
        return await codex.status(await actor(request))

    @app.post('/api/codex/login')
    async def codex_login(request: Request):
        return await codex.login(await actor(request,True))

    @app.post('/api/codex/logout')
    async def codex_logout(request: Request):
        return await codex.logout(await actor(request,True))

    @app.get('/api/codex/events')
    async def codex_events(request: Request, after: int = 0):
        if after < 0: raise HTTPException(422,'Invalid event sequence')
        return await codex.events_since(await actor(request),after)

    @app.post('/api/codex/interrupt')
    async def codex_interrupt(request: Request):
        return await codex.interrupt(await actor(request,True))

    @app.get('/api/codex/history')
    async def codex_history(request: Request, engagement_id: str):
        return await codex.history(await actor(request),engagement_id)

    @app.post('/api/codex/turn')
    async def codex_turn(request: Request):
        await actor(request,True)
        raise HTTPException(410,'Select Codex in Provider & model and use Tutor, Copilot, or Rabbit Hole through the shared AI workflow.')

    @app.get('/api/ai/settings')
    async def ai_settings(request: Request):
        owner=await actor(request)
        return await ai_status_for(owner)

    @app.put('/api/ai/settings')
    async def ai_select(spec: AISelection, request: Request):
        return providers.save_selection(await actor(request,True),spec)

    @app.put('/api/ai/keys/{provider}')
    async def ai_set_key(provider: str, spec: AIKeyChange, request: Request):
        providers.set_key(await actor(request,True),provider,spec)
        return {'saved':True}

    @app.delete('/api/ai/keys/{provider}')
    async def ai_clear_key(provider: str, request: Request):
        providers.remove_key(await actor(request,True),provider)
        return {'cleared':True}

    @app.get('/api/ai/models')
    async def ai_models(request: Request, provider: str, endpoint_id: str = ''):
        owner=await actor(request)
        if provider=='codex':
            if endpoint_id:raise HTTPException(422,'Codex does not use a local inference endpoint.')
            return {'models':await codex.models(owner),'endpoint_id':''}
        if provider not in PROVIDERS or PROVIDERS[provider]['cloud'] or endpoint_id not in providers.endpoints or providers.endpoints[endpoint_id]['provider'] != provider:
            raise HTTPException(422,'Choose a permitted local inference endpoint.')
        # Discovery is only permitted against server-approved endpoints. Never
        # follow redirects or accept a request-supplied URL/IP/path.
        import httpx
        base = providers.endpoints[endpoint_id]['url']
        url = base.rstrip('/') + ('/api/tags' if provider == 'ollama' else '/models')
        if provider != 'ollama' and not url.endswith('/v1/models'):
            url = base.rstrip('/') + '/v1/models'
        try:
            async with httpx.AsyncClient(timeout=8,follow_redirects=False,trust_env=False) as client:
                credential=providers.resolve_key(await actor(request),provider)
                headers={'Authorization':'Bearer '+credential} if credential else {}
                async with client.stream('GET',url,headers=headers) as reply:
                    if reply.status_code != 200:
                        raise HTTPException(502, f'Model discovery returned HTTP {reply.status_code}; you can enter a model ID manually.')
                    body=bytearray()
                    async for chunk in reply.aiter_bytes():
                        body.extend(chunk)
                        if len(body)>262144: raise HTTPException(502,'Model discovery response too large')
            payload=json.loads(body)
            candidates=payload.get('models',[]) if provider=='ollama' else payload.get('data',[])
            values=[]
            for item in candidates[:250]:
                mid=item.get('name' if provider=='ollama' else 'id') if isinstance(item,dict) else None
                if isinstance(mid,str) and 0<len(mid)<=160: values.append(mid)
            return {'models':values[:200],'endpoint_id':endpoint_id}
        except HTTPException:
            raise
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
            raise HTTPException(502,'Model discovery unavailable. Confirm the server is running and reachable from Kali; enter a model ID manually.') from exc

    @app.post('/api/ai/test')
    async def ai_test(request: Request):
        owner=await actor(request,True)
        route=providers.resolve(owner)
        # Explicit paid / local inference request; no evidence or chat history.
        result=await ai.gateway.complete(route,[{'role':'user','content':'Reply with OK to confirm this connection.'}],[])
        return {'connected':True,'provider':route['provider'],'model':route['model_id'],
                'reply':result['content'][:280], 'tool_support':'unverified; choose Copilot mode to check capability'}

    # The pet game has no AI dependency. Dialogue is an independent, opt-in layer.
    @app.get('/api/pet')
    async def pet_status(request: Request):
        return companion().snapshot(await actor(request))

    @app.post('/api/pet/hatch')
    async def pet_hatch(request: Request):
        return companion().hatch(await actor(request,True))

    @app.put('/api/pet/name')
    async def pet_name(spec: PetName, request: Request):
        owner=await actor(request,True)
        try: return companion().rename(owner,spec.name)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc

    @app.post('/api/pet/care')
    async def pet_care(spec: PetCare, request: Request):
        owner=await actor(request,True)
        try: return companion().care(owner,spec.action)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.put('/api/pet/tracking')
    async def pet_tracking(spec: PetTracking, request: Request):
        owner=await actor(request,True)
        try: return companion().tracking(owner,spec.enabled)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.get('/api/pet/context')
    async def pet_context(request: Request):
        return companion().operations(await actor(request))

    @app.put('/api/pet/context')
    async def pet_context_change(spec: PetContextToggle, request: Request):
        owner=await actor(request,True)
        try: return companion().set_operations(owner,spec.enabled)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.delete('/api/pet/context')
    async def pet_context_erase(request: Request):
        owner=await actor(request,True)
        try: return companion().clear_operations(owner)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.delete('/api/pet')
    async def pet_delete(request: Request):
        companion().delete(await actor(request,True))
        return {'deleted':True}

    @app.get('/api/pet/chat')
    async def pet_chat_history(request: Request):
        return conversation().history(await actor(request))

    @app.put('/api/pet/chat/mode')
    async def pet_chat_mode(spec: PetChatMode, request: Request):
        owner=await actor(request,True)
        try: return conversation().set_mode(owner,spec.mode)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.put('/api/pet/chat/focus')
    async def pet_chat_focus(spec: PetChatFocus, request: Request):
        owner=await actor(request,True)
        try: return conversation().remember_focus(owner,spec.focus)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.post('/api/pet/chat')
    async def pet_chat_send(spec: PetChatMessage, request: Request):
        owner=await actor(request,True)
        try: return await conversation().reply(owner,spec.message)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.delete('/api/pet/chat')
    async def pet_chat_clear(request: Request):
        owner=await actor(request,True)
        try: return conversation().clear(owner)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.get('/api/tools')
    async def tools(request: Request):
        await actor(request)
        return {'tools':registry.list(), 'profiles':PROFILES, 'scanned_at':registry.scanned}

    @app.post('/api/tools/refresh')
    async def refresh_tools(request: Request):
        await actor(request,True)
        await asyncio.to_thread(registry.scan)
        await asyncio.to_thread(discovery.rebuild)
        discovery.request_refresh(enrich_only=True)
        return {'tools':registry.list(), 'profiles':PROFILES, 'scanned_at':registry.scanned}

    # Read-only CLI intelligence. Never interpret documentation as execution policy.
    @app.get('/api/tool-intelligence')
    async def tool_intelligence_search(request: Request, query: str = ''):
        await actor(request)
        return {'tools': knowledge.search(query), 'online_enabled':cfg.docs_online}

    def tool_knowledge_error(exc):
        if isinstance(exc,PermissionError): return HTTPException(403,str(exc))
        if isinstance(exc,ValueError):
            return HTTPException(404,'Tool not installed or documentation request invalid')
        return HTTPException(503,'Documentation service temporarily unavailable')

    @app.get('/api/tool-intelligence/{name}')
    async def tool_intelligence_get(name: str, request: Request):
        owner=await actor(request)
        try: return await asyncio.to_thread(knowledge.get,name,owner=owner)
        except (ValueError,PermissionError) as exc: raise tool_knowledge_error(exc) from exc

    @app.post('/api/tool-intelligence/{name}/refresh')
    async def tool_intelligence_refresh(name: str, request: Request):
        owner=await actor(request,True)
        try: return await asyncio.to_thread(knowledge.get,name,refresh=True,owner=owner)
        except (ValueError,PermissionError) as exc: raise tool_knowledge_error(exc) from exc

    @app.post('/api/tool-intelligence/{name}/research')
    async def tool_intelligence_research(name: str, request: Request):
        await actor(request,True)
        try: return await asyncio.to_thread(knowledge.research,name)
        except (ValueError,PermissionError) as exc: raise tool_knowledge_error(exc) from exc
        except Exception: raise HTTPException(502,'Official documentation lookup failed; no commands were run.') from None

    @app.post('/api/tool-intelligence/{name}/search')
    async def tool_intelligence_online_search(name: str, request: Request):
        await actor(request,True)
        try: return await asyncio.to_thread(knowledge.search_web,name)
        except (ValueError,PermissionError) as exc: raise tool_knowledge_error(exc) from exc
        except Exception: raise HTTPException(502,'Approved documentation search failed; no commands were run.') from None

    @app.post('/api/tool-intelligence/{name}/notes')
    async def tool_intelligence_note(name: str, spec: ToolNote, request: Request):
        owner=await actor(request,True)
        try: return await asyncio.to_thread(knowledge.remember,name,spec.note,author=owner)
        except (ValueError,PermissionError) as exc: raise tool_knowledge_error(exc) from exc

    @app.post('/api/arguments/parse')
    async def parse_arguments(spec: ArgumentText, request: Request):
        await actor(request,True)
        try:
            args=shlex.split(spec.text)
        except ValueError as exc:
            raise HTTPException(400,'Unmatched quotes in arguments') from exc
        if any(a in ('|','||','&&',';','>','>>','<','&') for a in args):
            raise HTTPException(400,'Shell pipelines/redirection need the Terminal tab, not a foreground argv job')
        return {'args':args}

    @app.get('/api/engagements')
    async def engagements(request: Request):
        return store.list('engagement',await actor(request))

    @app.post('/api/engagements')
    async def new_engagement(spec: Engagement, request: Request):
        owner = await actor(request,True)
        eng = store.put('engagement',owner,spec.model_dump())
        store.workspace(eng['id']); store.event(owner,'engagement-created',eng['id'])
        return eng

    @app.put('/api/engagements/{id}')
    async def update_engagement(id: str, spec: Engagement, request: Request):
        owner = await actor(request,True)
        old = jobs.engagement(owner,id)
        result = store.put('engagement',owner,{**old,**spec.model_dump()})
        store.event(owner,'engagement-updated',id)
        return result

    @app.get('/api/proposals')
    async def proposals(request: Request, engagement_id: str = ''):
        owner = await actor(request)
        values = store.list('proposal',owner,engagement_id=engagement_id)
        return [dict(p,status='expired') if p['status']=='pending' and p['expires'] < time.time() else p
                for p in values if not engagement_id or p['engagement_id']==engagement_id]

    @app.post('/api/proposals')
    async def propose(spec: ProposalSpec, request: Request):
        return jobs.prepare(await actor(request,True),spec)

    @app.post('/api/registered-proposals')
    async def registered_propose(spec: RegisteredProposalSpec, request: Request):
        owner=await actor(request,True)
        policy=rabbit.policy.current()
        adapter=policy.get('registered_adapters',{}).get(spec.profile)
        if policy['status']!='active' or not adapter or spec.profile not in policy['enabled_profiles']:
            raise HTTPException(403,'Administrator has not enabled this registered adapter')
        return jobs.prepare_registered(owner,spec.engagement_id,adapter,spec.target,
            spec.parameters,spec.reason,policy['revision'],'adapter-preview')

    @app.post('/api/proposals/{id}/approve')
    async def approve(id: str, spec: Approval, request: Request):
        return await jobs.approve(await actor(request,True),id,spec.digest,spec.authorized)

    @app.post('/api/proposals/{id}/dismiss')
    async def dismiss(id: str, request: Request):
        owner = await actor(request,True)
        p = store.get('proposal',id,owner)
        if not p: raise HTTPException(404,'Proposal not found')
        if p['status'] == 'pending':
            p['status']='dismissed'; store.put('proposal',owner,p)
        return {'status':p['status']}

    @app.get('/api/engagements/{id}/graph')
    async def graph_read(id: str, request: Request):
        return graph.get(await actor(request),id)

    @app.put('/api/engagements/{id}/graph/notes')
    async def graph_note(id: str, request: Request):
        owner=await actor(request,True)
        payload=await request.json()
        if not isinstance(payload,dict) or set(payload)!={'node_id','note'} or not isinstance(payload['node_id'],str):
            raise HTTPException(422,'Expected node_id and note only')
        return graph.annotate(owner,id,payload['node_id'],payload['note'])

    @app.get('/api/jobs')
    async def list_jobs(request: Request, engagement_id: str = ''):
        values = store.list('job',await actor(request),engagement_id=engagement_id)
        return [x for x in values if not engagement_id or x['engagement_id']==engagement_id]

    @app.get('/api/jobs/{id}/output')
    async def output(id: str, request: Request, offset: int = 0):
        return jobs.output(id,await actor(request),offset)

    @app.post('/api/jobs/{id}/stop')
    async def stop_job(id: str, request: Request):
        return await jobs.stop(await actor(request,True),id)

    @app.delete('/api/jobs/{id}')
    async def delete_job(id: str, request: Request):
        return await jobs.delete(await actor(request,True),id)

    @app.post('/api/jobs-stop-all')
    async def stop_jobs(request: Request):
        owner = await actor(request,True)
        results = []
        for job_id in list(jobs.tasks):
            if store.get('job',job_id,owner): results.append(await jobs.stop(owner,job_id))
        return {'requested':len(results),'note':'Managed jobs only; terminal sessions are separate.'}

    @app.get('/api/terminals')
    async def list_terminals(request: Request):
        owner = await actor(request)
        return [s.public() for s in terminals.sessions.values() if s.owner == owner]

    @app.post('/api/terminals')
    async def new_terminal(spec: SessionSpec, request: Request):
        return await terminals.create(await actor(request,True),spec.engagement_id)

    @app.delete('/api/terminals/{id}')
    async def close_terminal(id: str, request: Request):
        await terminals.close(await actor(request,True),id)
        return {'closed':True}

    @app.post('/api/terminals/{id}/ticket')
    async def terminal_ticket(id: str, request: Request):
        owner = await actor(request,True)
        terminals.get(owner,id)
        return {'ticket':auth.ticket(owner,id),'expires_in':30}

    @app.websocket('/ws/terminals/{id}')
    async def terminal_socket(ws: WebSocket, id: str):
        session = queue = None
        workers = []
        try:
            who = await auth.actor(ws)
            auth.origin(ws)
            if not auth.consume_ticket(ws.query_params.get('ticket',''),who.name,id):
                await ws.close(code=1008); return
            session, queue = terminals.attach(who.name,id)
            history = list(session.history)
            await ws.accept()
            await ws.send_json({'type':'ready','id':id,'history_truncated':session.truncated})
            for piece in history:
                await ws.send_json({'type':'output','data':base64.b64encode(piece).decode('ascii')})
            async def send():
                while True:
                    try: msg = await asyncio.wait_for(queue.get(),20)
                    except asyncio.TimeoutError: msg = {'type':'ping'}
                    await ws.send_json(msg)
                    if msg['type'] in ('gap','closed','exit'): return
            async def receive():
                while True:
                    raw = await ws.receive_text()
                    if len(raw) > 20000: raise ValueError('Frame too large')
                    msg = json.loads(raw)
                    if msg.get('type') == 'input':
                        await terminals.write(session,str(msg.get('data','')))
                    elif msg.get('type') == 'resize':
                        terminals.resize(session,msg.get('rows',28),msg.get('cols',100))
                    elif msg.get('type') != 'pong': raise ValueError('Unknown frame')
            workers = [asyncio.create_task(send()),asyncio.create_task(receive())]
            budget = max(1,min(900,who.expires-int(time.time())))
            await asyncio.wait_for(asyncio.wait(workers,return_when=asyncio.FIRST_COMPLETED),budget)
        except (HTTPException,WebSocketDisconnect,OSError,ValueError,RuntimeError,TimeoutError):
            pass
        finally:
            for worker in workers: worker.cancel()
            if workers: await asyncio.gather(*workers,return_exceptions=True)
            if session and queue: terminals.detach(session,queue)
            try: await ws.close(code=1000)
            except (RuntimeError,WebSocketDisconnect): pass

    @app.get('/api/chat')
    async def history(request: Request, engagement_id: str):
        owner = await actor(request)
        jobs.engagement(owner,engagement_id)
        return list(reversed(store.list('chat',owner,60,engagement_id=engagement_id)))

    @app.post('/api/chat')
    async def chat(spec: ChatSpec, request: Request):
        return await ai.chat(await actor(request,True),spec)

    @app.delete('/api/chat')
    async def clear_chat(request: Request, engagement_id: str):
        owner=await actor(request,True)
        jobs.engagement(owner,engagement_id)
        with store.db() as connection:
            connection.execute("DELETE FROM records WHERE kind='chat' AND owner=? AND json_extract(data, '$.engagement_id')=?", (owner, engagement_id))
        return {'cleared':True}

    @app.get('/api/engagements/{id}/files')
    async def files(id: str, request: Request):
        owner=await actor(request); jobs.engagement(owner,id)
        return list_files(store.workspace(id))

    @app.post('/api/engagements/{id}/files')
    async def upload(id: str, request: Request):
        owner=await actor(request,True); jobs.engagement(owner,id)
        name=unquote(request.headers.get('x-filename',''))
        if not name or len(name)>200 or name in ('.','..') or any(c in name for c in '/\\\x00') or any(ord(c)<32 for c in name):
            raise HTTPException(400,'Upload needs a simple filename without path separators')
        dest=store.workspace(id)/name
        try: fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        except FileExistsError as exc: raise HTTPException(409,'A file with that name already exists. Rename the upload; existing evidence is never overwritten.') from exc
        total=0
        try:
            with os.fdopen(fd,'wb') as f:
                async for chunk in request.stream():
                    total+=len(chunk)
                    if total>MAX_UPLOAD: raise HTTPException(413,'File is larger than 10 MiB')
                    f.write(chunk)
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        store.event(owner,'file-uploaded',f'{id}/{name}')
        return {'path':name,'size':total}

    @app.get('/api/engagements/{id}/files/{path:path}')
    async def download(id: str, path: str, request: Request):
        owner=await actor(request); jobs.engagement(owner,id)
        file=safe_open(store.workspace(id),path)
        def chunks():
            with file:
                while data:=file.read(65536): yield data
        return StreamingResponse(chunks(),media_type='application/octet-stream',headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(Path(path).name,safe='')})

    @app.get('/api/engagements/{id}/export')
    async def export(id: str, request: Request, files: bool = False):
        owner=await actor(request); eng=jobs.engagement(owner,id)
        data=await asyncio.to_thread(export_evidence,store,jobs,owner,eng,files)
        store.event(owner,'evidence-exported',id)
        return Response(data,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="foxworx-{id[:8]}-evidence.zip"'})

    @app.get('/api/audit')
    async def audit(request: Request):
        return store.events(await actor(request))

    app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
    return app
