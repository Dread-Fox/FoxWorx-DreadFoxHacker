"""Distribution-contract regression checks for the v2.9 CLI expansion."""
from pathlib import Path
from foxworx import __version__
from foxworx.command_templates import validate_library

ROOT = Path(__file__).resolve().parents[1]


def test_release_identity_is_coherent_across_cli_and_web():
    assert __version__ == '3.3.3'
    assert 'v3.3.3' in (ROOT/'static/index.html').read_text().lower()
    assert 'v3.3.3' in (ROOT/'foxworx/cli.py').read_text().lower()
    assert 'FoxWorx-DreadFoxHacker-v3.3.3' in (ROOT/'docs/INSTALL.md').read_text()


def test_curated_adapter_library_covers_requested_cli_families():
    library = validate_library()
    assert len(library) >= 19
    expected = {'nuclei','nikto','ffuf','gobuster','feroxbuster','sqlmap',
        'wapiti','testssl','sslyze','masscan','rustscan','theHarvester',
        'amass','subfinder','enum4linux-ng','smbclient','httpx-toolkit','dnsrecon'}
    assert expected <= {item['tool'] for item in library.values()}
    assert all(item['mode'] == 'review' for item in library.values() if item['risk'] == 'intrusive')
