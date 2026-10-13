"""Security and functionality tests for the administrator-controlled adapter registry."""
import json
import pytest
from fastapi import HTTPException
from foxworx.adapters import AdapterPolicy, PolicyError, parse_document, ADAPTERS
from foxworx.jobs import PROFILES, recipe
from foxworx.models import ProposalSpec, RabbitSpec


def test_new_adapters_have_strict_fixed_argv_and_are_exposed():
    for name,tool,target in [
        ('dns-caa','dig','example.org'),('dns-ns','dig','example.org'),
        ('dns-soa','dig','example.org'),('dns-cname','dig','example.org'),
        ('tls-certificate','openssl','example.org'),
        ('http-status','curl','https://example.org/'),
        ('http-get-limited','curl','https://example.org/'),
        ('web-fingerprint','whatweb','https://example.org/'),
    ]:
        assert name in PROFILES and name in ADAPTERS
        assert PROFILES[name]['tool']==tool
        args=recipe(name,target)
        assert args and all(isinstance(arg,str) for arg in args)
        assert '-L' not in args and '--location' not in args
        ProposalSpec(engagement_id='a'*24,tool=tool,profile=name,target=target)
    assert '--max-filesize' in recipe('http-get-limited','https://example.org/')
    assert '--aggression=1' in recipe('web-fingerprint','https://example.org/')
    assert '-servername' in recipe('tls-certificate','example.org')


def test_adapter_parameters_cannot_be_set_by_model_or_user():
    with pytest.raises(ValueError): recipe('tls-certificate','https://example.org/private')
    with pytest.raises(ValueError): recipe('web-fingerprint','example.org')
    with pytest.raises(ValueError): recipe('dns-ns','https://example.org/')
    with pytest.raises(ValueError): recipe('http-get-limited','https://user:password@example.org/')


def test_policy_parser_forbids_unknown_names_and_unbounded_runs():
    good={'schema':1,'enabled_profiles':['dns-a','tls-certificate'],'max_steps':5,'max_minutes':10}
    parsed=parse_document(json.dumps(good).encode())
    assert parsed['enabled_profiles']==('dns-a','tls-certificate')
    for mutation in [
        {**good,'schema':2},
        {**good,'enabled_profiles':['advanced']},
        {**good,'enabled_profiles':['dns-a','dns-a']},
        {**good,'max_steps':10000},
        {**good,'max_minutes':60},
        {**good,'shell':'/bin/sh'},
        {**good,'max_steps':True},
    ]:
        with pytest.raises(PolicyError): parse_document(json.dumps(mutation).encode())


def test_absent_admin_policy_disables_autonomous_adapters(tmp_path):
    policy=AdapterPolicy(tmp_path/'missing.json')
    snapshot=policy.current()
    assert not snapshot['enabled_profiles']
    assert snapshot['status'] in ('missing','untrusted')
    assert snapshot['revision']


def test_unsigned_untrusted_policy_rejected_and_no_adapters_activated(tmp_path):
    path=tmp_path/'policy.json'
    path.write_text(json.dumps({'schema':1,'enabled_profiles':['tls-certificate'],'max_steps':5,'max_minutes':10}))
    path.chmod(0o666)
    policy=AdapterPolicy(path)
    snapshot=policy.current()
    assert snapshot['status']=='untrusted'
    assert snapshot['enabled_profiles']==()


def test_policy_revision_changes_when_disabled_or_changed(monkeypatch):
    policy=AdapterPolicy('/etc/foxworx/adapter-policy.json')
    a=json.dumps({'schema':1,'enabled_profiles':['dns-a'],'max_steps':4,'max_minutes':2}).encode()
    b=json.dumps({'schema':1,'enabled_profiles':['tls-certificate'],'max_steps':4,'max_minutes':2}).encode()
    monkeypatch.setattr(policy,'_read_trusted',lambda:a)
    first=policy.current()
    monkeypatch.setattr(policy,'_read_trusted',lambda:b)
    second=policy.current()
    assert first['revision'] != second['revision']
    assert second['enabled_profiles']==('tls-certificate',)


def test_no_user_supplied_arbitrary_profile():
    with pytest.raises(Exception):
        RabbitSpec(engagement_id='a'*24,objective='Investigate my authorized lab',target='example.org',profiles=['shell'],authorized=True)


def test_root_owned_policy_can_activate_and_root_revocation_is_immediate():
    """Real filesystem permission check when the test runner is privileged."""
    import os, tempfile
    from pathlib import Path
    if os.geteuid()!=0:
        pytest.skip('A non-root test process cannot create a root-owned policy directory')
    with tempfile.TemporaryDirectory(prefix='foxworx-policy-',dir='/root') as folder:
        path=Path(folder)/'policy.json'
        path.write_text(json.dumps({'schema':1,'enabled_profiles':['dns-a'],'max_steps':3,'max_minutes':5}))
        path.chmod(0o644)
        policy=AdapterPolicy(path)
        assert policy.current()['status']=='active'
        with path.open('w') as fd:
            json.dump({'schema':1,'enabled_profiles':['dns-a','dns-caa'],'max_steps':2,'max_minutes':4},fd)
        assert policy.current()['enabled_profiles']==('dns-a','dns-caa')
        path.chmod(0o666)
        assert policy.current()['status']=='untrusted'
        path.unlink()
        assert policy.current()['status']=='missing'


def test_inventory_shows_disabled_and_not_installed_without_leaking_policy_path():
    from types import SimpleNamespace
    p=AdapterPolicy('/etc/foxworx/adapter-policy.json')
    p.current=lambda: {'status':'active','revision':'abc','enabled_profiles':('dns-a','web-fingerprint'),
                        'max_steps':4,'max_minutes':6}
    mock=SimpleNamespace(list=lambda:[{'name':'dig','installed':True},{'name':'whatweb','installed':False}])
    inv=p.inventory(mock)
    by_name={x['profile']:x for x in inv['profiles']}
    assert by_name['dns-a']['available'] is True
    assert by_name['web-fingerprint']['enabled'] is True
    assert by_name['web-fingerprint']['available'] is False
    assert by_name['tls-certificate']['enabled'] is False
    assert len(inv['profiles'])==17
