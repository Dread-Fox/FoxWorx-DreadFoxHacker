"""Workspace file handling and bounded evidence exports; never follow symlinks."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import stat
import zipfile
from fastapi import HTTPException

MAX_UPLOAD = 10 * 1024 * 1024
MAX_EXPORT = 64 * 1024 * 1024


def safe_open(root: Path, relative: str):
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(p in ('..', '.', '') for p in path.parts) or '\x00' in relative:
        raise HTTPException(400, 'Invalid workspace path')
    descriptors = []
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in path.parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        file_fd = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            os.close(file_fd)
            raise HTTPException(400, 'Only regular files can be downloaded')
        return os.fdopen(file_fd, 'rb')
    except OSError as exc:
        raise HTTPException(404, 'File missing, inaccessible, or symlink not permitted') from exc
    finally:
        for fd in descriptors:
            os.close(fd)


def list_files(root: Path) -> dict:
    files = []
    limited = False
    for directory, subdirs, names in os.walk(root, followlinks=False):
        subdirs[:] = sorted(d for d in subdirs if not (Path(directory)/d).is_symlink())
        for name in sorted(names):
            p = Path(directory)/name
            try:
                if p.is_symlink() or not p.is_file():
                    continue
                info = p.stat()
                files.append({'path':p.relative_to(root).as_posix(), 'size':info.st_size, 'modified':info.st_mtime})
            except OSError:
                continue
            if len(files) >= 1000:
                limited = True
                break
        if limited: break
    return {'files':files, 'limited':limited}


def export_evidence(store, jobs, owner: str, engagement: dict, include_files: bool = False) -> bytes:
    records = store.list('job', owner, 10001, engagement_id=engagement['id'])
    if len(records) > 10000:
        raise HTTPException(413, 'More than 10,000 jobs in this engagement. Archive the state locally; this export will not silently omit records.')
    if any(j['status'] in ('queued','running','stopping') for j in records):
        raise HTTPException(409, 'Stop or finish active jobs before exporting a consistent evidence bundle')
    memory = io.BytesIO()
    manifest, total = [], 0
    with zipfile.ZipFile(memory, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        def add(name: str, data: bytes):
            nonlocal total
            total += len(data)
            if total > MAX_EXPORT:
                raise HTTPException(413, 'Export exceeds 64 MiB. Download individual files or archive locally.')
            z.writestr(name, data)
            manifest.append({'path':name, 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
        add('engagement.json', json.dumps(engagement, indent=2).encode())
        add('jobs.json', json.dumps(records, indent=2).encode())
        for job in records:
            for name in ('combined.log','stdout.log','stderr.log'):
                path = jobs.directory / job['id'] / name
                if path.is_file() and not path.is_symlink():
                    if path.stat().st_size > MAX_EXPORT-total: raise HTTPException(413, 'Evidence exceeds export limit')
                    add(f'jobs/{job["id"]}/{name}', path.read_bytes())
        if include_files:
            root = store.workspace(engagement['id'])
            listing = list_files(root)
            if listing['limited']:
                raise HTTPException(413, 'More than 1000 workspace files. Export selected files locally.')
            for item in listing['files']:
                if item['size'] > MAX_EXPORT-total: raise HTTPException(413, 'Workspace exceeds export limit')
                with safe_open(root, item['path']) as f:
                    data = f.read(MAX_EXPORT-total+1)
                add('workspace/' + item['path'], data)
        report = f'''# {engagement['name']} — assessment notes\n\n## Authorization and scope\nRefer to engagement.json; operator-supplied, not proof of program approval.\n\n## Observations\n{engagement.get('notes','')}\n\n## Findings requiring validation\nAdd reproduction steps, impact, minimal evidence and remediation here. Tool output alone is not a confirmed vulnerability.\n\n## Evidence\n{len(records)} recorded managed jobs. See jobs.json and manifest.json.\nTerminal keystrokes and complete terminal transcripts are not included.\n\n## Disclosure review\nRemove credentials, personal data and unrelated records before sharing.\n'''
        add('report-draft.md', report.encode())
        z.writestr('manifest.json', json.dumps({'files':manifest,'note':'Checksums detect later byte changes; they are not signed provenance or tamper-proof audit.'},indent=2))
    return memory.getvalue()
