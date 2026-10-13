from pathlib import Path
import importlib.util
import stat
import pytest

def cli_module():
    assert importlib.util.find_spec('foxworx.cli') is not None, 'distributable needs configuration and doctor commands'
    from foxworx import cli
    return cli

def test_init_config_safe_and_idempotent(tmp_path):
    cli=cli_module(); path=tmp_path/'config/settings.env'
    assert cli.initialize(path) is True
    raw=path.read_text(); assert len(raw)>100
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    assert cli.initialize(path) is False
    assert path.read_text()==raw
    from foxworx.config import Settings
    cfg=Settings.load(path)
    assert cfg.local_token=='' and cfg.mode=='open'

def test_config_write_rejects_symlinks(tmp_path):
    cli=cli_module(); target=tmp_path/'target'; target.write_text('unchanged')
    link=tmp_path/'link'; link.symlink_to(target)
    with pytest.raises(ValueError): cli.write_settings(link,{'A':'b'})
    assert target.read_text()=='unchanged'

def test_cli_version_no_secrets(capsys):
    cli=cli_module()
    assert cli.main(['version'])==0
    assert capsys.readouterr().out.strip()=='3.3.3'

def test_vendor_hashes_are_complete():
    cli=cli_module()
    assert cli.vendor_check()==[]
    import json
    manifest=json.loads((Path(cli.ROOT)/'static/vendor/manifest.json').read_text())
    assert len(manifest['files'])==4


def test_init_workstation_profile(tmp_path):
    cli=cli_module(); cfgfile=tmp_path/'settings.env'
    assert cli.initialize(cfgfile, profile='workstation') is True
    from dotenv import dotenv_values
    values=dotenv_values(cfgfile, interpolate=False)
    assert values['FOXWORX_MAX_JOBS']=='4'
    assert values['FOXWORX_MAX_TERMINALS']=='8'
    assert values['FOXWORX_RESERVE_MIB']=='1024'
    assert cli.initialize(cfgfile,profile='pi') is False
    assert dotenv_values(cfgfile, interpolate=False)==values


def test_init_pi_profile(tmp_path):
    cli=cli_module(); cfgfile=tmp_path/'settings.env'
    assert cli.initialize(cfgfile, profile='pi') is True
    from dotenv import dotenv_values
    values=dotenv_values(cfgfile, interpolate=False)
    assert values['FOXWORX_MAX_JOBS']=='2'
    assert values['FOXWORX_MAX_TERMINALS']=='4'


def test_doctor_reports_host_without_pi_warning(tmp_path, monkeypatch, capsys):
    from foxworx import cli
    from foxworx.platforms import detect_host
    info=detect_host(machine='x86_64',system='Linux',os_release='ID=kali',model='')
    monkeypatch.setattr('foxworx.platforms.host_snapshot',lambda **kwargs:info)
    from foxworx.config import Settings
    cfg=Settings(state=tmp_path/'state',secret='s'*48,local_token='t'*48,config_path=tmp_path/'cfg.env')
    assert cli.doctor(cfg) == (1 if __import__('os').geteuid()==0 else 0)
    result=__import__('json').loads(capsys.readouterr().out)
    assert result['hardware']['architecture']=='x86_64'
    assert not any('Not an ARM64 Pi' in x for x in result['warnings'])
