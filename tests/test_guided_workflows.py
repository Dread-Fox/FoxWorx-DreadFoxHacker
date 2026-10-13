from foxworx.jobs import PROFILES, recipe
from foxworx.models import ProposalSpec


def test_more_bounded_workflows_are_exposed_and_can_be_prepared():
    expected={'tcp-web','dns-aaaa','dns-mx','dns-txt','http-options'}
    assert expected <= set(PROFILES)
    for profile in expected:
        target='http://127.0.0.1/' if profile.startswith('http-') else '127.0.0.1'
        params=recipe(profile,target)
        assert params and isinstance(params,list)
        ProposalSpec(engagement_id='a'*24,tool=PROFILES[profile]['tool'],profile=profile,target=target)


def test_dns_variants_do_not_accept_arbitrary_dns_names_or_commands():
    for profile in ('dns-aaaa','dns-mx','dns-txt'):
        args=recipe(profile,'example.org')
        assert args[-2]=='example.org' and args[-1] in ('AAAA','MX','TXT')
    assert '--max-rate' in recipe('tcp-web','127.0.0.1')


def test_http_options_is_verb_only_no_redirect_and_no_credentials():
    args=recipe('http-options','https://example.org/')
    assert '--request' in args and 'OPTIONS' in args
    assert '-L' not in args
    assert '--proto' in args
