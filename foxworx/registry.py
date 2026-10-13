"""Inventory executables and metadata without blindly invoking --help/--version."""
from pathlib import Path
import configparser
import json
import os
import re
import shlex
import subprocess
import time
from .config import Settings

NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+-]{0,149}$')
CATALOG = json.loads(Path(__file__).with_name('catalog.json').read_text())

class Registry:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.items: dict[str, dict] = {}
        self.scanned = 0.0

    def scan(self) -> list[dict]:
        found = {}
        for directory in self.cfg.tool_path.split(':'):
            p = Path(directory)
            if not p.is_dir():
                continue
            try:
                for f in p.iterdir():
                    if NAME.fullmatch(f.name) and f.name not in found and f.is_file() and os.access(f, os.X_OK):
                        found[f.name] = str(f.absolute())
            except PermissionError:
                continue
        versions = {}
        try:
            r = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'], capture_output=True, text=True, timeout=5, check=False)
            for line in r.stdout.splitlines():
                if '\t' in line:
                    p, v = line.split('\t', 1)
                    versions[p.split(':')[0]] = v
        except (OSError, subprocess.TimeoutExpired):
            pass
        items = {}
        for name in set(CATALOG) | set(found):
            meta = CATALOG.get(name, {'category':'System / additional', 'mode':'unknown', 'package':'',
                                      'description':'Discovered executable; no specialized adapter',
                                      'note':'Verify invocation and dependencies. Interactive/GUI requirements have not been classified.'})
            items[name] = {'name':name, **meta, 'path':found.get(name), 'installed':name in found,
                           'curated':name in CATALOG, 'version':versions.get(meta['package'], '')}
        # Read launch metadata, never execute .desktop command strings.
        for directory in ('/usr/share/applications', '/usr/share/kali-menu/applications'):
            for file in list(Path(directory).glob('*.desktop'))[:3000]:
                try:
                    if file.stat().st_size > 65536:
                        continue
                    ini = configparser.ConfigParser(interpolation=None, strict=False)
                    ini.read(file)
                    entry = ini['Desktop Entry']
                    command = shlex.split(entry.get('Exec', ''))
                    if command:
                        name = Path(command[0]).name
                        if name in items and name not in CATALOG:
                            items[name]['mode'] = 'interactive' if entry.get('Terminal', 'false').lower() == 'true' else 'gui'
                            items[name]['description'] = entry.get('Comment', entry.get('Name', name))[:240]
                            items[name]['note'] = 'Mode inferred from desktop entry; verify any headless alternative.'
                except (OSError, ValueError, KeyError, configparser.Error):
                    pass
        self.items = items
        self.scanned = time.time()
        return self.list()

    def list(self) -> list[dict]:
        if not self.scanned:
            return self.scan()
        return sorted(self.items.values(), key=lambda x: (not x['curated'], x['name'].lower()))

    def resolve(self, name: str) -> dict:
        if not NAME.fullmatch(name):
            raise ValueError('Select a discovered executable name, not a path or command line')
        if not self.scanned:
            self.scan()
        item = self.items.get(name)
        if not item or not item['installed']:
            raise ValueError(f'{name} is not installed/discovered. Install it separately, then refresh the toolbox.')
        path = Path(item['path'])
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f'{name} is no longer executable; refresh the toolbox')
        return dict(item)

    @staticmethod
    def fingerprint(path: str) -> dict:
        p = Path(path)
        s = p.stat()
        return {'realpath':str(p.resolve()), 'inode':s.st_ino, 'size':s.st_size, 'mtime_ns':s.st_mtime_ns}
