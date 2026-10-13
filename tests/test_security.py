import asyncio
from dataclasses import replace
import time
from types import SimpleNamespace
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from foxworx.auth import Auth
from foxworx.config import child_environment

@pytest.fixture
def cf_auth(cfg):
    cfg=replace(cfg,mode='cloudflare',origin='https://kali.example.test',cf_team='https://foxteam.cloudflareaccess.com',cf_aud='app-aud',emails=('operator@example.test',))
    cfg.validate(); auth=Auth(cfg)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    auth.jwks=SimpleNamespace(get_signing_key_from_jwt=lambda raw:SimpleNamespace(key=key.public_key()))
    return auth,key

def token(auth,key,**changes):
    claims={'sub':'identity-id','email':'operator@example.test','aud':auth.cfg.cf_aud,'iss':auth.cfg.cf_team,'iat':int(time.time())-1,'exp':int(time.time())+60}
    claims.update(changes)
    return jwt.encode(claims,key,algorithm='RS256')

def test_cf_accepts_valid_signature_allowlisted_identity(cf_auth):
    auth,key=cf_auth
    assert auth.verify_cloudflare(token(auth,key)).name=='operator@example.test'

@pytest.mark.parametrize('changes',[{'aud':'other-app'},{'iss':'https://other.cloudflareaccess.com'},{'exp':1},{'email':'intruder@example.test'}])
def test_cf_rejects_wrong_audience_issuer_expiry_identity(cf_auth,changes):
    auth,key=cf_auth
    with pytest.raises(HTTPException): auth.verify_cloudflare(token(auth,key,**changes))

def test_cf_rejects_forged_signature_and_unsigned(cf_auth):
    auth,key=cf_auth
    other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    with pytest.raises(HTTPException): auth.verify_cloudflare(token(auth,other))
    with pytest.raises(HTTPException): auth.verify_cloudflare(jwt.encode({'email':'operator@example.test'},'',algorithm='none'))

def test_ws_ticket_bound_one_use_and_expiry(cfg):
    auth=Auth(cfg)
    t=auth.ticket('alice','one')
    assert auth.consume_ticket(t,'alice','one') is True
    assert auth.consume_ticket(t,'alice','one') is False
    t=auth.ticket('alice','one')
    assert auth.consume_ticket(t,'bob','one') is False
    t=auth.ticket('alice','one'); auth.tickets[t]=('alice','one',time.time()-1)
    assert auth.consume_ticket(t,'alice','one') is False

def test_child_environment_does_not_inherit_provider_or_injection_vars(cfg,monkeypatch):
    for key in ['OPENAI_API_KEY','FOXWORX_LOCAL_TOKEN','LD_PRELOAD','PYTHONPATH','HTTPS_PROXY','BASH_ENV']:
        monkeypatch.setenv(key,'must-not-inherit')
    env=child_environment(cfg)
    assert 'must-not-inherit' not in env.values()
    assert env['TERM']=='xterm-256color'
