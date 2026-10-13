import pytest
from foxworx.scope import allowed, normalize_target

@pytest.mark.parametrize('target,expected', [
 ('a.example.test', True), ('deep.a.example.test', True), ('example.test', False),
 ('badexample.test', False), ('a.example.test.evil.test', False), ('blocked.example.test', False)])
def test_wildcard_boundary_and_exclusions(target, expected):
 assert allowed(target, ['*.example.test'], ['blocked.example.test']) is expected

def test_cidr_and_exact_ip():
 assert allowed('192.0.2.2', ['192.0.2.0/24'], [])
 assert not allowed('192.0.3.2', ['192.0.2.0/24'], [])
 assert not allowed('some.example.test', ['192.0.2.0/24'], [])

def test_url_scope_is_not_hostwide():
 assert allowed('https://example.test/app/a', ['https://example.test/app'], [])
 assert not allowed('https://example.test/application', ['https://example.test/app'], [])
 assert not allowed('example.test', ['https://example.test/app'], [])
 assert not allowed('http://example.test/app', ['https://example.test/app'], [])

@pytest.mark.parametrize('target', ['-oNfile', 'a;id', 'a b', 'https://u:p@example.test/', 'https://x.test/../admin', 'https://x.test/%2e%2e/admin'])
def test_reject_malformed_target(target):
 with pytest.raises(ValueError): normalize_target(target)
