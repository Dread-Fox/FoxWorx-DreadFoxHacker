"""Portable, bounded hardware discovery for Kali ARM64 and AMD64 nodes.

Never installs drivers, grants capabilities, exposes GPU UUIDs, or executes
model code. nvidia-smi data is advisory and not proof of CUDA readiness.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

ARCHITECTURES = {'aarch64': 'aarch64', 'arm64': 'aarch64',
                 'x86_64': 'x86_64', 'amd64': 'x86_64'}
_GPU_QUERY = '--query-gpu=index,uuid,name,memory.total,memory.free,driver_version'
_CACHE: tuple[float, dict] | None = None


def normalize_architecture(machine: str) -> str:
    return ARCHITECTURES.get(machine.strip().lower(), 'unsupported')


def require_host_architecture(machine: str, system: str) -> str:
    if system != 'Linux':
        raise ValueError('FOXWORX service requires Linux (Kali ARM64 or Kali x86-64); Windows and macOS hosts are not supported')
    arch = normalize_architecture(machine)
    if arch == 'unsupported':
        raise ValueError('FOXWORX supports Linux x86-64 and ARM64, not ' + machine)
    return arch


def profile_defaults(profile: str) -> dict[str, int]:
    presets = {'pi': {'max_jobs':2, 'max_terminals':4, 'reserve_mib':256},
               'workstation': {'max_jobs':4, 'max_terminals':8, 'reserve_mib':1024}}
    if profile not in presets:
        raise ValueError('Unknown host profile')
    return dict(presets[profile])


def parse_nvidia_smi(stdout: str) -> list[dict]:
    """Parse only stable, limited GPU fields; never expose unique hardware IDs."""
    import csv
    gpus = []
    for row in csv.reader(stdout.splitlines()[:32], skipinitialspace=True):
        if len(row) != 6 or len(gpus) >= 16:
            continue
        try:
            index = int(row[0].strip())
            total, free = int(row[3].strip()), int(row[4].strip())
            if not (0 <= index < 128 and 0 <= free <= total <= 1000000):
                continue
        except ValueError:
            continue
        gpus.append({'index':index, 'name':row[2].strip()[:80],
                     'memory_mib':total, 'free_mib':free,
                     'driver_version':row[5].strip()[:40]})
    return gpus


def _read(path: str, size: int = 4096) -> str:
    try:
        with open(path, 'rb') as stream:
            return stream.read(size).decode('utf-8','replace').strip('\0\n ')
    except (OSError, UnicodeError):
        return ''


def _distro(os_release: str) -> str:
    for line in os_release.splitlines():
        if line.startswith('ID='):
            return line.partition('=')[2].strip().strip('"\'').lower()[:50]
    return 'unknown'


def detect_host(*, machine: str | None = None, system: str | None = None,
                os_release: str | None = None, model: str | None = None) -> dict:
    machine = machine if machine is not None else platform.machine()
    system = system if system is not None else platform.system()
    os_release = os_release if os_release is not None else _read('/etc/os-release')
    model = model if model is not None else _read('/proc/device-tree/model')
    arch = normalize_architecture(machine)
    supported = system == 'Linux' and arch != 'unsupported'
    profile = 'pi' if arch == 'aarch64' else 'workstation'
    distro = _distro(os_release)
    info = {'architecture':arch, 'raw_architecture':machine[:48],
            'os':system, 'distro':distro, 'profile':profile,
            'device':('Raspberry Pi' if 'Raspberry Pi' in model else 'Linux host'),
            'supported':supported, 'cpu_count':os.cpu_count() or 1,
            'gpus':[], 'gpu_count':0, 'gpu_status':'nvidia-smi-not-found',
            'ollama_installed':bool(shutil.which('ollama')),
            'warnings':[]}
    if not supported:
        info['warnings'].append('Only native Linux ARM64 and x86-64 hosts are supported.')
    if distro != 'kali':
        info['warnings'].append('Not identified as Kali Linux; some Kali tools and package names may differ.')
    path = shutil.which('nvidia-smi')
    if path:
        try:
            completed = subprocess.run([path, _GPU_QUERY, '--format=csv,noheader,nounits'],
                                       text=True, capture_output=True, check=False, timeout=3)
            if completed.returncode == 0:
                info['gpus'] = parse_nvidia_smi(completed.stdout)
                info['gpu_status'] = 'available' if info['gpus'] else 'no-devices'
            else:
                info['gpu_status'] = 'probe-failed'
                info['warnings'].append('NVIDIA query failed; inspect the host driver with nvidia-smi locally.')
        except subprocess.TimeoutExpired:
            info['gpu_status'] = 'probe-timeout'
            info['warnings'].append('NVIDIA query timed out; the workbench can still run without it.')
        except OSError:
            info['gpu_status'] = 'probe-failed'
            info['warnings'].append('NVIDIA driver utility was found but could not run.')
    info['gpu_count'] = len(info['gpus'])
    if arch == 'x86_64' and info['gpu_count'] == 0:
        info['warnings'].append('No NVIDIA GPUs reported; install/verify drivers separately if local CUDA inference is wanted.')
    return info


def host_snapshot(*, fresh: bool = False) -> dict:
    global _CACHE
    now = time.monotonic()
    if fresh or _CACHE is None or now - _CACHE[0] >= 30:
        _CACHE = (now, detect_host())
    return _CACHE[1]


def main() -> int:
    parser = argparse.ArgumentParser(description='FOXWORX host preflight (does not modify the computer)')
    parser.add_argument('--require', action='store_true', help='fail if the host is unsupported')
    parser.add_argument('--profile', action='store_true', help='print only the default host profile')
    args = parser.parse_args()
    info = host_snapshot(fresh=True)
    if args.profile:
        print(info['profile'] if info['supported'] else 'unsupported')
    else:
        print(json.dumps(info, indent=2))
    if args.require and not info['supported']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
