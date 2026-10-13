"""Token-free v3.3.3: local and reverse-proxied browser API share one operator."""
from dataclasses import replace
from pathlib import Path
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from foxworx.app import create_app
from foxworx.cli import initialize, write_settings, main
from foxworx.config import Settings


def test_fresh_install_defaults_to_open_no_local_setup_token(tmp_path, monkeypatch):
    for k in ('FOXWORX_AUTH_MODE','FOXWORX_PORT','FOXWORX_ORIGIN','FOXWORX_LOCAL_TOKEN'):
        monkeypatch.delenv(k,raising=False)
    p=tmp_path/'settings.env'
    initialize(p,profile='pi')
    values=dotenv_values(p,interpolate=False)
    assert values['FOXWORX_AUTH_MODE']=='open'
    assert values['FOXWORX_PORT']=='8765'
    assert values['FOXWORX_LOCAL_TOKEN']==''
    assert len(values['FOXWORX_SESSION_SECRET'])>=32  # Still used for CSRF protection.
    assert Settings.load(p).mode=='open'


def test_operator_gets_full_session_locally_and_through_any_tunnel_hostname(cfg):
    opened=replace(cfg,mode='open',local_token='',public_origin='')
    for base in ('http://127.0.0.1:8765',
                 'https://foxworxhacker1.dreadfoxtrader.com',
                 'https://another-approved-by-operator.example'):
        with TestClient(create_app(opened,_allow_root_for_tests=True),base_url=base,
                        client=('127.0.0.1',62000)) as c:
            assert c.get('/').status_code==200
            assert c.get('/api/auth-mode').json()['mode']=='open'
            resp=c.get('/api/session')
            assert resp.status_code==200,resp.text
            state=resp.json()
            assert state['actor']=='local-operator' and len(state['csrf'])==64
            assert 'foxworx_local' not in c.cookies
            assert c.post('/api/login',json={'token':'unused'},headers={'Origin':base}).status_code==404
            # The current browser works with its own origin regardless of proxy hostname.
            h={'Origin':base,'X-Foxworx-CSRF':state['csrf']}
            assert c.post('/api/logout',json={},headers=h).status_code==200
            assert c.get('/api/session').status_code==200
            assert c.post('/api/logout',json={},headers={'Origin':base}).status_code==403
            assert c.post('/api/logout',json={},headers={'X-Foxworx-CSRF':state['csrf']}).status_code==403


def test_legacy_config_converts_to_token_free_and_preserves_data(tmp_path, monkeypatch):
    for k in ('FOXWORX_AUTH_MODE','FOXWORX_PORT','FOXWORX_ORIGIN'):
        monkeypatch.delenv(k,raising=False)
    path=tmp_path/'settings.env'
    initialize(path,profile='pi')
    old=dict(dotenv_values(path,interpolate=False))
    old.update({'FOXWORX_AUTH_MODE':'local', 'FOXWORX_PORT':'8000',
                'FOXWORX_ORIGIN':'https://old-tunnel.example',
                'FOXWORX_LOCAL_TOKEN':'x'*48,
                'OPENAI_API_KEY':'preserve-test-credential',
                'FOXWORX_DISCORD_BOT_TOKEN':'preserve-test-bot',
                'FOXWORX_DISCORD_CHANNEL_ID':'123456789012345678'})
    write_settings(path,old)
    assert main(['configure','--config',str(path),'--local-service'])==0
    data=dict(dotenv_values(path,interpolate=False))
    assert data['FOXWORX_AUTH_MODE']=='open'
    assert data['FOXWORX_PORT']=='8765'
    assert data['FOXWORX_LOCAL_TOKEN']==old['FOXWORX_LOCAL_TOKEN']  # Unused, not rotated.
    for name in ('OPENAI_API_KEY','FOXWORX_DISCORD_BOT_TOKEN','FOXWORX_DISCORD_CHANNEL_ID','FOXWORX_SESSION_SECRET','FOXWORX_STATE'):
        assert data[name]==old[name]
    assert path.with_name('settings.env.before-v3.3.3').is_file()
    assert Settings.load(path).mode=='open'
    assert main(['configure','--config',str(path),'--local-service'])==0
    assert dict(dotenv_values(path,interpolate=False))==data


def test_open_mode_does_not_require_cloudflare_identity_or_host_allowlist(cfg):
    opened=replace(cfg,mode='open',local_token='',public_origin='')
    with TestClient(create_app(opened,_allow_root_for_tests=True),
                    base_url='https://foxworxhacker1.dreadfoxtrader.com',
                    client=('203.0.113.52',60001)) as c:
        assert c.get('/api/auth-mode',headers={'Host':'rewritten.proxy.internal',
                    'X-Forwarded-For':'203.0.113.52', 'CF-Ray':'proxy-id'}).status_code==200
        assert c.get('/api/session').status_code==200
        h={'Origin':'https://foxworxhacker1.dreadfoxtrader.com',
           'X-Foxworx-CSRF':c.get('/api/session').json()['csrf'],
           'Host':'rewritten.proxy.internal'}
        assert c.post('/api/logout',json={},headers=h).status_code==200
