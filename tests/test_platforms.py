"""Portable host detection must not depend on a particular CPU/GPU."""
import subprocess
from types import SimpleNamespace
import pytest
from foxworx import platforms


@pytest.mark.parametrize(('machine','expected'), [('x86_64','x86_64'),('amd64','x86_64'),('AMD64','x86_64'),('aarch64','aarch64'),('arm64','aarch64')])
def test_architecture_aliases(machine, expected):
    assert platforms.normalize_architecture(machine)==expected


def test_reject_other_architectures():
    with pytest.raises(ValueError, match='x86-64.*ARM64'):
        platforms.require_host_architecture('armv7l', 'Linux')
    with pytest.raises(ValueError, match='Linux'):
        platforms.require_host_architecture('x86_64', 'Windows')


def test_gpu_query_parsing_multiple_cards():
    sample='0, GPU-123, NVIDIA GeForce RTX 3060 Ti, 8192, 7000, 580.67\n1, GPU-234, NVIDIA GeForce RTX 3060 Ti, 8192, 6900, 580.67\n2, GPU-345, NVIDIA GeForce RTX 3060 Ti, 8192, 6800, 580.67\n'
    rows=platforms.parse_nvidia_smi(sample)
    assert len(rows)==3
    assert [g['index'] for g in rows]==[0,1,2]
    assert all(g['memory_mib']==8192 for g in rows)
    assert rows[0]['name']=='NVIDIA GeForce RTX 3060 Ti'
    assert 'uuid' not in rows[0]  # sensitive identifiers should not go to browser


def test_detect_no_gpu_does_not_block(monkeypatch):
    monkeypatch.setattr(platforms.shutil, 'which', lambda name: None)
    info=platforms.detect_host(machine='aarch64',system='Linux',os_release='ID=kali\n',model='Raspberry Pi 4 Model B Rev 1.4')
    assert info['supported']
    assert info['profile']=='pi'
    assert info['gpu_count']==0
    assert info['gpu_status']=='nvidia-smi-not-found'
    assert info['distro']=='kali'


def test_detect_workstation_gpus(monkeypatch):
    monkeypatch.setattr(platforms.shutil,'which',lambda name: '/usr/bin/nvidia-smi' if name=='nvidia-smi' else None)
    gpu_data='0, GPU-1, NVIDIA RTX 3060 Ti, 8192, 8000, 580.67\n1, GPU-2, NVIDIA RTX 3060 Ti, 8192, 7999, 580.67\n2, GPU-3, NVIDIA RTX 3060 Ti, 8192, 7998, 580.67\n'
    def fake_run(args,**kwargs):
        assert args[0]=='/usr/bin/nvidia-smi'
        assert kwargs['timeout'] <= 5
        return SimpleNamespace(returncode=0,stdout=gpu_data,stderr='')
    monkeypatch.setattr(platforms.subprocess,'run',fake_run)
    info=platforms.detect_host(machine='x86_64',system='Linux',os_release='ID=kali\n',model='')
    assert info['profile']=='workstation'
    assert info['gpu_count']==3
    assert info['gpus'][2]['memory_mib']==8192
    assert info['gpu_status']=='available'


def test_failing_gpu_probe_is_warning_not_failure(monkeypatch):
    monkeypatch.setattr(platforms.shutil,'which',lambda name: '/usr/bin/nvidia-smi' if name=='nvidia-smi' else None)
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired('nvidia-smi',3)
    monkeypatch.setattr(platforms.subprocess,'run',timeout)
    info=platforms.detect_host(machine='x86_64',system='Linux',os_release='ID=kali\n',model='')
    assert info['supported']
    assert info['gpu_count']==0
    assert info['gpu_status']=='probe-timeout'


def test_platform_defaults():
    assert platforms.profile_defaults('pi')=={'max_jobs':2,'max_terminals':4,'reserve_mib':256}
    assert platforms.profile_defaults('workstation')=={'max_jobs':4,'max_terminals':8,'reserve_mib':1024}
    with pytest.raises(ValueError): platforms.profile_defaults('other')
