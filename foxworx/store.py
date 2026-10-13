"""Small persistent store. All API-visible records are bound to an actor."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import secrets
import sqlite3


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def identifier() -> str:
    return secrets.token_hex(12)


class Store:
    def __init__(self, state: Path):
        self.state = state
        self.pet_observer = None  # Optional best-effort, nonblocking audit action observer.
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        state.chmod(0o700)
        self.path = state / 'workbench-v2.sqlite3'
        with self.db() as c:
            c.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL, id TEXT NOT NULL, owner TEXT NOT NULL,
                    data TEXT NOT NULL, created TEXT NOT NULL,
                    PRIMARY KEY(kind,id));
                CREATE INDEX IF NOT EXISTS by_owner ON records(kind,owner,created);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, owner TEXT NOT NULL,
                    action TEXT NOT NULL, details TEXT NOT NULL);
                PRAGMA user_version=2;
            ''')
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def put(self, kind: str, owner: str, data: dict) -> dict:
        data = dict(data)
        data.setdefault('id', identifier())
        data.setdefault('created', now())
        with self.db() as c:
            row = c.execute('SELECT owner FROM records WHERE kind=? AND id=?', (kind, data['id'])).fetchone()
            if row and row['owner'] != owner:
                raise PermissionError('Record owner mismatch')
            c.execute('INSERT INTO records VALUES(?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data',
                      (kind, data['id'], owner, json.dumps(data, ensure_ascii=False), data['created']))
        return data

    def get(self, kind: str, id: str, owner: str) -> dict | None:
        with self.db() as c:
            row = c.execute('SELECT data FROM records WHERE kind=? AND id=? AND owner=?', (kind, id, owner)).fetchone()
        return json.loads(row['data']) if row else None

    def list(self, kind: str, owner: str, limit: int = 200, engagement_id: str = '') -> list[dict]:
        query = 'SELECT data FROM records WHERE kind=? AND owner=?'
        parameters = [kind, owner]
        if engagement_id:
            query += " AND json_extract(data, '$.engagement_id')=?"
            parameters.append(engagement_id)
        query += ' ORDER BY created DESC, rowid DESC LIMIT ?'
        parameters.append(limit)
        with self.db() as c:
            rows = c.execute(query, parameters).fetchall()
        return [json.loads(r['data']) for r in rows]

    def all(self, kind: str) -> list[tuple[str, dict]]:
        with self.db() as c:
            rows = c.execute('SELECT owner,data FROM records WHERE kind=?', (kind,)).fetchall()
        return [(r['owner'], json.loads(r['data'])) for r in rows]

    def delete(self, kind: str, id: str, owner: str) -> bool:
        with self.db() as c:
            return bool(c.execute('DELETE FROM records WHERE kind=? AND id=? AND owner=?', (kind, id, owner)).rowcount)

    def event(self, owner: str, action: str, details: str = '') -> None:
        with self.db() as c:
            c.execute('INSERT INTO audit(ts,owner,action,details) VALUES(?,?,?,?)', (now(), owner, action, details[:2000]))
        # Never pass sensitive audit details into the pet subsystem.
        observer = self.pet_observer
        if observer is not None:
            try:
                observer(owner, action)
            except Exception:
                pass  # A game observer must not make operational audit or jobs fail.

    def events(self, owner: str, limit: int = 200) -> list[dict]:
        with self.db() as c:
            rows = c.execute('SELECT * FROM audit WHERE owner=? ORDER BY id DESC LIMIT ?', (owner, limit)).fetchall()
        return [dict(r) for r in rows]

    def workspace(self, engagement_id: str) -> Path:
        if len(engagement_id) != 24 or any(c not in '0123456789abcdef' for c in engagement_id):
            raise ValueError('Invalid engagement identifier')
        root = self.state / 'workspaces' / engagement_id
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return root
