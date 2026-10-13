"""Provider-normalized LiteLLM and native Codex completions. NEVER runs tools."""
from __future__ import annotations
import asyncio
from fastapi import HTTPException


def make_tools(names: set[str] | None = None) -> list[dict]:
    from .ai import TOOLS
    return [{'type':'function','function':{'name':t['name'],'description':t['description'],
            'parameters':t['parameters']}} for t in TOOLS if names is None or t['name'] in names]


class ModelGateway:
    def __init__(self, completion=None, codex=None):
        self.completion = completion
        self.codex = codex

    async def complete(self, route: dict, messages: list[dict], tools: list[dict]) -> dict:
        if route.get('provider') == 'codex':
            if self.codex is None:
                raise HTTPException(503,'Codex provider transport is unavailable.')
            return await self.codex.complete(route['owner'], route['model_id'], messages, tools)
        handler = self.completion
        if handler is None:
            try:
                from litellm import acompletion
                handler = acompletion
            except ImportError as exc:
                raise HTTPException(503,'Optional LiteLLM dependency missing. Install requirements-ai.txt to enable multi-provider AI.') from exc
        args = {'model':route['model'],'messages':messages,'timeout':40,'num_retries':0,'max_tokens':2400}
        if route.get('api_key'):
            args['api_key']=route['api_key']
        elif route.get('api_base') and route.get('provider') in ('lmstudio','vllm','custom'):
            # OpenAI-compatible SDK clients otherwise fall back to ambient
            # OPENAI_API_KEY, potentially leaking it to a self-hosted server.
            args['api_key']='foxworx-local-no-secret'
        if route.get('api_base'): args['api_base']=route['api_base']
        if tools: args['tools']=tools; args['tool_choice']='auto'
        try:
            async with asyncio.timeout(48):
                response=await handler(**args)
            if hasattr(response,'model_dump'): response=response.model_dump()
            result=response['choices'][0]['message']
            if hasattr(result,'model_dump'): result=result.model_dump()
            calls=[]
            for item in (result.get('tool_calls') or [])[:3]:
                fn=item.get('function') or {}
                if item.get('type')=='function' and isinstance(fn.get('arguments'),str) and fn.get('name'):
                    calls.append({'id':item.get('id',''), 'name':fn['name'], 'arguments':fn['arguments']})
            body=result.get('content')
            if isinstance(body,list):
                body='\n'.join(p.get('text','') for p in body if isinstance(p,dict) and p.get('type')=='text')
            if body is None: body=''
            if not isinstance(body,str): raise ValueError('Malformed AI content')
            return {'content':body,'calls':calls,'original':result}
        except HTTPException:
            raise
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise HTTPException(504,'Model request timed out; no proposed command was executed.') from exc
        except Exception as exc:
            # Provider exceptions may contain access keys, model prompts, URLs, or
            # sensitive response bodies. Never send their .args/.message to clients.
            category=type(exc).__name__.lower()
            if 'authentication' in category or 'permission' in category:
                detail='Model provider rejected the credentials or account permission.'
            elif 'ratelimit' in category or 'quota' in category:
                detail='Model provider rate limit or quota reached.'
            elif 'notfound' in category:
                detail='The model was not found or is unavailable for these credentials.'
            elif 'badrequest' in category or 'unsupported' in category:
                detail='Model rejected the request or tool-calling format. Check this model’s supported capabilities; Tutor mode may work.'
            elif 'connection' in category:
                detail='Could not reach the configured inference server. Check it is running and accessible from the Pi.'
            else:
                detail='Model request failed or returned an unsupported response. No command was executed.'
            raise HTTPException(502,detail) from None
