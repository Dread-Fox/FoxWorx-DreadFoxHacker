"""User-selected inference providers; locally approved endpoints and sealed per-actor keys.

No browser-configurable URL is ever used for outbound model requests.
Keys are encrypted at rest with a key derived from the configured FOXWORX session
secret; keep that secret backed up and never reuse it outside this installation.
"""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import re
from urllib.parse import urlsplit
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from .models import AISelection, AIKeyChange

PROVIDERS = {
    'openai': {'label':'OpenAI', 'prefix':'openai/', 'cloud':True, 'examples':['gpt-4o','gpt-4.1','gpt-5']},
    'codex': {'label':'Codex · ChatGPT', 'prefix':'codex/', 'cloud':True, 'examples':['default']},
    'anthropic': {'label':'Anthropic Claude', 'prefix':'anthropic/', 'cloud':True, 'examples':['claude-sonnet-4-5','claude-opus-4-1']},
    'gemini': {'label':'Google Gemini', 'prefix':'gemini/', 'cloud':True, 'examples':['gemini-2.5-pro','gemini-2.5-flash']},
    'xai': {'label':'xAI Grok', 'prefix':'xai/', 'cloud':True, 'examples':['grok-4']},
    'deepseek': {'label':'DeepSeek', 'prefix':'deepseek/', 'cloud':True, 'examples':['deepseek-chat','deepseek-reasoner']},
    'mistral': {'label':'Mistral AI', 'prefix':'mistral/', 'cloud':True, 'examples':['mistral-large-latest','mistral-small-latest']},
    'ollama': {'label':'Ollama · local', 'prefix':'ollama_chat/', 'cloud':False, 'examples':['qwen3:8b','llama3.1:8b']},
    'lmstudio': {'label':'LM Studio · local', 'prefix':'openai/', 'cloud':False, 'examples':[]},
    'vllm': {'label':'vLLM · self-hosted', 'prefix':'openai/', 'cloud':False, 'examples':[]},
    'custom': {'label':'Custom OpenAI-compatible', 'prefix':'openai/', 'cloud':False, 'examples':[]},
}
LOCAL_ENDPOINTS = {
    'ollama-local': {'provider':'ollama','url':'http://127.0.0.1:11434'},
    'lmstudio-local': {'provider':'lmstudio','url':'http://127.0.0.1:1234/v1'},
}
ENV_KEYS = {'openai':'api_key','anthropic':'anthropic_api_key','gemini':'gemini_api_key',
            'xai':'xai_api_key','deepseek':'deepseek_api_key','mistral':'mistral_api_key'}
MODEL_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._:/+@-]{0,159}$')
ENDPOINT_RE = re.compile(r'^[a-z][a-z0-9-]{0,39}$')


def normalize_model(provider: str, model: str) -> str:
    if provider not in PROVIDERS or not isinstance(model, str):
        raise ValueError('Unrecognized AI provider')
    if model != model.strip() or any(ord(c) < 32 for c in model):
        raise ValueError('Invalid model identifier')
    prefix = PROVIDERS[provider]['prefix']
    if provider == 'codex' and not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}', model):
        raise ValueError('Enter a Codex model ID or default, without a provider prefix')
    if not MODEL_RE.fullmatch(model) or model.startswith(('/', '.')) or '..' in model or model.endswith('/'):
        raise ValueError('Invalid model identifier')
    # A model identifier may include a slash (namespaced HF/hosted models), but
    # it must not smuggle another routing prefix into this configured provider.
    if '/' in model and model.split('/', 1)[0].lower() in set(PROVIDERS) | {'openai','ollama_chat','hosted_vllm','vertex_ai'}:
        raise ValueError('Enter only the model ID, without another provider prefix')
    return prefix + model


def approved_endpoint_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 400 or '\\' in value or '%' in value:
        raise ValueError('Invalid approved endpoint URL')
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or not p.netloc or p.username or p.password or p.query or p.fragment:
        raise ValueError('Approved model endpoints must be absolute HTTP(S) URLs without credentials, query or fragment')
    if p.path not in ('', '/', '/v1', '/v1/') or p.port == 0:
        raise ValueError('Endpoint path may be empty or /v1 only')
    if any(ch.isspace() or ord(ch)<32 for ch in value):
        raise ValueError('Whitespace is not permitted in model endpoint URLs')
    return value.rstrip('/')


def owner_id(owner: str, suffix: str) -> str:
    return hashlib.sha256((owner + '\0' + suffix).encode()).hexdigest()[:40]


class ProviderManager:
    def __init__(self, cfg, store, codex=None):
        self.cfg, self.store = cfg, store
        self.codex = codex
        salt = b'foxworx-ai-credential-encryption-v2.1\0'
        self.fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(salt+(cfg.ai_encryption_key or cfg.secret).encode()).digest()))
        self.endpoints = dict(LOCAL_ENDPOINTS)
        for key, item in cfg.ai_endpoints.items():
            if not ENDPOINT_RE.fullmatch(key) or key in self.endpoints or not isinstance(item,dict) or item.get('provider') not in PROVIDERS or PROVIDERS[item['provider']]['cloud']:
                raise ValueError('FOXWORX_AI_ENDPOINTS must contain unique, named local/self-hosted provider routes')
            self.endpoints[key] = {'provider':item['provider'], 'url':approved_endpoint_url(item.get('url',''))}

    def endpoints_for(self, provider: str) -> list[dict]:
        return [{'id':key, 'provider':value['provider'], 'label':key} for key,value in self.endpoints.items() if value['provider']==provider]

    def resolve_key(self, owner: str, provider: str) -> str:
        stored = self.store.get('ai_key',owner_id(owner,provider),owner)
        if stored:
            try:
                return self.fernet.decrypt(stored['ciphertext'].encode()).decode()
            except (InvalidToken, ValueError, KeyError) as exc:
                raise HTTPException(503,'Saved AI credential could not be decrypted. Re-enter it; check for a rotated FOXWORX_SESSION_SECRET.') from exc
        return str(getattr(self.cfg, ENV_KEYS.get(provider,''), '') or '')

    def set_key(self, owner: str, provider: str, change: AIKeyChange) -> None:
        if provider == 'codex' or provider not in PROVIDERS or not PROVIDERS[provider]['cloud'] and provider not in ('custom','lmstudio','vllm'):
            raise HTTPException(400,'API credentials are not applicable for this provider')
        secret = change.api_key.strip()
        if not secret or len(secret) > 4096 or any(ord(c)<32 for c in secret):
            raise HTTPException(422,'API key cannot be blank and must not contain control characters')
        self.store.put('ai_key',owner,{'id':owner_id(owner,provider),'ciphertext':self.fernet.encrypt(secret.encode()).decode()})
        self.store.event(owner,'ai-credential-updated',provider)

    def remove_key(self, owner: str, provider: str) -> None:
        if provider not in PROVIDERS: raise HTTPException(404,'Unknown provider')
        self.store.delete('ai_key',owner_id(owner,provider),owner)
        self.store.event(owner,'ai-credential-cleared',provider)

    def selection(self, owner: str) -> dict:
        stored = self.store.get('ai_selection',owner_id(owner,'current'),owner)
        if stored: return {k:stored[k] for k in ('provider','model','endpoint_id')}
        if self.cfg.api_key and self.cfg.model:
            return {'provider':'openai','model':self.cfg.model,'endpoint_id':''}
        return {'provider':'','model':'','endpoint_id':''}

    def save_selection(self, owner: str, choice: AISelection) -> dict:
        provider = choice.provider
        try: normalize_model(provider,choice.model)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        endpoint_id = choice.endpoint_id
        if PROVIDERS[provider]['cloud']:
            if endpoint_id: raise HTTPException(422,'Cloud providers do not use local endpoints')
        else:
            if endpoint_id not in self.endpoints or self.endpoints[endpoint_id]['provider'] != provider:
                raise HTTPException(422,'Choose an administrator-approved endpoint for this provider')
        self.store.put('ai_selection',owner,{'id':owner_id(owner,'current'),'provider':provider,'model':choice.model.strip(),'endpoint_id':endpoint_id})
        self.store.event(owner,'ai-model-selected',provider)
        return self.describe(owner)

    def resolve(self, owner: str) -> dict:
        choice = self.selection(owner)
        provider = choice['provider']
        if provider not in PROVIDERS or not choice['model']:
            raise HTTPException(503,'AI not configured. Choose a provider and model in AI Settings.')
        try: model=normalize_model(provider,choice['model'])
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        if provider == 'codex':
            if not self.codex or not self.codex.installed():
                raise HTTPException(503,'Codex CLI is not installed or is not on the configured tool path.')
            return {'provider':provider,'model':model,'model_id':choice['model'],
                    'owner':owner,'api_key':'','api_base':''}
        key=self.resolve_key(owner,provider)
        endpoint = ''
        if PROVIDERS[provider]['cloud']:
            if not key: raise HTTPException(503,f'Configure an API key for {PROVIDERS[provider]["label"]} in AI Settings.')
        else:
            if choice['endpoint_id'] not in self.endpoints or self.endpoints[choice['endpoint_id']]['provider']!=provider:
                raise HTTPException(503,'Selected inference endpoint is no longer approved on this node.')
            endpoint=self.endpoints[choice['endpoint_id']]['url']
        return {'provider':provider,'model':model,'model_id':choice['model'],'api_key':key,'api_base':endpoint}

    def describe(self, owner: str) -> dict:
        selection=self.selection(owner)
        provider=selection['provider']
        rows=[]
        for key, info in PROVIDERS.items():
            credential=bool(self.store.get('ai_key',owner_id(owner,key),owner)) or bool(getattr(self.cfg,ENV_KEYS.get(key,''),''))
            native = key == 'codex'
            rows.append({'id':key,'label':info['label'],'cloud':info['cloud'], 'requires_key':info['cloud'] and not native,
                         'auth_method':'chatgpt' if native else 'api_key',
                         'requires_endpoint':not info['cloud'],
                         'has_key':credential,'examples':info['examples'],'endpoints':self.endpoints_for(key),
                         'tool_support':'model-dependent; unverified until tested'})
        ready = False
        if provider in PROVIDERS and selection['model']:
            try:
                normalize_model(provider,selection['model'])
                if provider == 'codex':
                    ready = bool(self.codex and self.codex.installed() and self.codex.accounts.get(owner,{}).get('connected'))
                else:
                    ready = (bool(self.store.get('ai_key',owner_id(owner,provider),owner)) or bool(getattr(self.cfg,ENV_KEYS.get(provider,''),''))) if PROVIDERS[provider]['cloud'] else selection['endpoint_id'] in {r['id'] for r in self.endpoints_for(provider)}
            except ValueError: pass
        return {'selected':selection,'providers':rows,'ready':ready,
                'engine_installed':bool(self.codex and self.codex.installed()) if provider == 'codex' else importlib.util.find_spec('litellm') is not None,
                'notice':'Keys encrypted on this Pi. Cloud requests leave the Pi. Endpoint choices are administrator controlled; model tool calling is not guaranteed.'}
