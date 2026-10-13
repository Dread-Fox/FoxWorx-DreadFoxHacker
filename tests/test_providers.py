import pytest
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from foxworx.providers import ProviderManager, normalize_model, approved_endpoint_url, owner_id
from foxworx.models import AISelection, AIKeyChange


def test_provider_routing_and_model_validation():
    assert normalize_model('anthropic','claude-example') == 'anthropic/claude-example'
    assert normalize_model('gemini','gemini-pro-example') == 'gemini/gemini-pro-example'
    assert normalize_model('ollama','qwen3:8b') == 'ollama_chat/qwen3:8b'
    assert normalize_model('lmstudio','local-llm') == 'openai/local-llm'
    for provider, model in [('anthropic','openai/gpt'), ('custom','../../thing'),('ollama','\nsecret'), ('bad','model')]:
        with pytest.raises((ValueError, HTTPException)):
            normalize_model(provider, model)


def test_endpoints_only_admin_approved(cfg,store):
    manager=ProviderManager(cfg,store)
    assert manager.endpoints_for('ollama')[0]['id']=='ollama-local'
    with pytest.raises(HTTPException):
        manager.save_selection('alice',AISelection(provider='vllm',model='my-model',endpoint_id='http://127.0.0.1:8999'))
    with pytest.raises(HTTPException):
        manager.save_selection('alice',AISelection(provider='ollama',model='qwen3',endpoint_id='lmstudio-local'))
    cfg.ai_endpoints={'gpu':{'provider':'vllm','url':'http://192.168.1.10:8000/v1'}}
    manager=ProviderManager(cfg,store)
    selection=manager.save_selection('alice',AISelection(provider='vllm',model='my-model',endpoint_id='gpu'))
    assert selection['ready']
    assert manager.resolve('alice')['api_base']=='http://192.168.1.10:8000/v1'


def test_secrets_encrypted_per_operator_and_not_readable_via_metadata(cfg,store):
    manager=ProviderManager(cfg,store)
    manager.set_key('alice','anthropic',AIKeyChange(api_key='sk-test-alice-personal-secret'))
    manager.set_key('bob','anthropic',AIKeyChange(api_key='sk-test-bob-personal-secret'))
    a=store.get('ai_key',owner_id('alice','anthropic'),'alice')
    assert 'sk-test-alice-personal-secret' not in str(a)
    assert manager.resolve_key('alice','anthropic')=='sk-test-alice-personal-secret'
    assert manager.resolve_key('bob','anthropic')=='sk-test-bob-personal-secret'
    assert 'sk-test' not in str(manager.describe('alice'))
    manager.remove_key('alice','anthropic')
    assert manager.resolve_key('alice','anthropic')==''
    assert manager.resolve_key('bob','anthropic')!=''


def test_local_selection_no_key_and_cloud_requires_key(cfg,store):
    manager=ProviderManager(cfg,store)
    r=manager.save_selection('alice',AISelection(provider='ollama',model='qwen3:8b',endpoint_id='ollama-local'))
    assert r['ready'] and r['selected']['model']=='qwen3:8b'
    r=manager.save_selection('alice',AISelection(provider='openai',model='gpt-4o'))
    assert not r['ready']
    manager.set_key('alice','openai',AIKeyChange(api_key='test-key'))
    assert manager.describe('alice')['ready']


def test_endpoint_validation_rejects_auth_query_and_bad_scheme():
    for url in ['file:///etc/passwd','http://root:pwd@localhost:1234/v1','http://localhost:1234/v1?token=abc','http://localhost:1234/#private','http://localhost:1234/../../x']:
        with pytest.raises(ValueError): approved_endpoint_url(url)
    assert approved_endpoint_url('http://127.0.0.1:11434')=='http://127.0.0.1:11434'

def test_credential_encryption_survives_auth_secret_rotation(cfg,store):
    cfg.ai_encryption_key='stable-model-vault-key-'+'x'*48
    manager=ProviderManager(cfg,store)
    manager.set_key('alice','openai',AIKeyChange(api_key='secret-that-must-survive'))
    cfg.secret='changed-auth-secret-'+'n'*48
    after=ProviderManager(cfg,store)
    assert after.resolve_key('alice','openai')=='secret-that-must-survive'


def test_key_records_use_user_derived_ids(cfg,store):
    manager=ProviderManager(cfg,store)
    manager.save_selection('alice',AISelection(provider='ollama',model='qwen3',endpoint_id='ollama-local'))
    manager.save_selection('bob',AISelection(provider='ollama',model='llama3.1',endpoint_id='ollama-local'))
    assert manager.selection('alice')['model']=='qwen3'
    assert manager.selection('bob')['model']=='llama3.1'
