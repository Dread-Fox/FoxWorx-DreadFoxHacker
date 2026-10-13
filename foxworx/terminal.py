"""Persistent in-service PTYs. Browser disconnects detach, never replay input."""
from __future__ import annotations
import asyncio
import base64
from collections import deque
from dataclasses import dataclass, field
import fcntl
import os
from pathlib import Path
import pty
import signal
import struct
import sys
import termios
import time
from fastapi import HTTPException
from .config import Settings, child_environment
from .store import Store, identifier, now

@dataclass
class TerminalSession:
    id: str
    owner: str
    engagement_id: str
    master: int
    process: asyncio.subprocess.Process
    created: str = field(default_factory=now)
    detached_at: float = field(default_factory=time.time)
    history: deque = field(default_factory=deque)
    history_bytes: int = 0
    truncated: bool = False
    subscribers: set = field(default_factory=set)
    eof: bool = False
    watcher: asyncio.Task | None = None

    def public(self) -> dict:
        return {'id':self.id, 'engagement_id':self.engagement_id, 'created':self.created,
                'connected':bool(self.subscribers), 'pid':self.process.pid,
                'status':'exited' if self.process.returncode is not None else 'running',
                'returncode':self.process.returncode, 'history_truncated':self.truncated}


class TerminalManager:
    def __init__(self, cfg: Settings, store: Store):
        self.cfg, self.store = cfg, store
        self.sessions: dict[str, TerminalSession] = {}
        self.lock = asyncio.Lock()
        self.reaper = None

    def get(self, owner, id) -> TerminalSession:
        session = self.sessions.get(id)
        if not session or session.owner != owner:
            raise HTTPException(404, 'Terminal no longer exists. Create a new session; service restart ends sessions.')
        return session

    async def create(self, owner: str, engagement_id: str) -> dict:
        async with self.lock:
            if not self.store.get('engagement', engagement_id, owner):
                raise HTTPException(404, 'Engagement not found')
            if len(self.sessions) >= self.cfg.max_terminals:
                raise HTTPException(429, 'Terminal limit reached. Close an existing session before creating another.')
            master, slave = pty.openpty()
            try:
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 28, 100, 0, 0))
                process = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).with_name('pty_child.py')),
                            self.cfg.shell, '-i', stdin=slave, stdout=slave, stderr=slave,
                            env=child_environment(self.cfg), cwd=self.store.workspace(engagement_id))
            except Exception:
                os.close(master)
                raise
            finally:
                os.close(slave)
            os.set_blocking(master, False)
            session = TerminalSession(identifier(), owner, engagement_id, master, process)
            self.sessions[session.id] = session
            asyncio.get_running_loop().add_reader(master, self._readable, session)
            session.watcher = asyncio.create_task(self._watch(session))
            self.store.event(owner, 'terminal-created', session.id)
            return session.public()

    def _publish(self, s: TerminalSession, message: dict):
        for queue in list(s.subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Slow browsers are detached, not allowed to block/consume unbounded RAM.
                s.subscribers.discard(queue)
                if not s.subscribers: s.detached_at = time.time()
                while not queue.empty(): queue.get_nowait()
                queue.put_nowait({'type':'gap', 'message':'Output exceeded browser throughput. Reconnect to the retained terminal buffer.'})

    def _readable(self, s: TerminalSession):
        try:
            data = os.read(s.master, 16384)
        except BlockingIOError:
            return
        except OSError:
            data = b''
        if not data:
            asyncio.get_running_loop().remove_reader(s.master)
            s.eof = True
            return
        s.history.append(data)
        s.history_bytes += len(data)
        while s.history_bytes > 262144 and len(s.history) > 1:
            s.history_bytes -= len(s.history.popleft())
            s.truncated = True
        self._publish(s, {'type':'output', 'data':base64.b64encode(data).decode('ascii')})

    async def _watch(self, s):
        await s.process.wait()
        self._publish(s, {'type':'exit', 'returncode':s.process.returncode})
        self.store.event(s.owner, 'terminal-shell-exited', s.id)

    def attach(self, owner: str, id: str) -> tuple[TerminalSession, asyncio.Queue]:
        s = self.get(owner, id)
        q = asyncio.Queue(maxsize=128)
        s.subscribers.add(q)
        return s, q

    def detach(self, s, queue):
        s.subscribers.discard(queue)
        if not s.subscribers:
            s.detached_at = time.time()

    async def write(self, s: TerminalSession, text: str):
        if s.process.returncode is not None:
            raise HTTPException(409, 'The shell has exited. Create a new terminal.')
        data = text.encode('utf-8')
        if len(data) > 16384:
            raise HTTPException(413, 'Paste is too large. Upload a file instead.')
        end = asyncio.get_running_loop().time() + 2
        while data:
            try:
                n = os.write(s.master, data)
                data = data[n:]
            except BlockingIOError:
                if asyncio.get_running_loop().time() > end:
                    raise HTTPException(429, 'Terminal input is backlogged. Retry after the program responds.')
                await asyncio.sleep(.01)

    def resize(self, s, rows, cols):
        rows, cols = max(5, min(150, int(rows))), max(20, min(300, int(cols)))
        fcntl.ioctl(s.master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

    @staticmethod
    def _session_pids(session_id: int) -> list[int]:
        pids = []
        for path in Path('/proc').glob('[0-9]*/stat'):
            try:
                parts = path.read_text().rsplit(')', 1)[1].split()
                if int(parts[3]) == session_id and path.parent.stat().st_uid == os.getuid():
                    pids.append(int(path.parent.name))
            except (OSError, ValueError, IndexError):
                pass
        return pids

    async def close(self, owner: str, id: str):
        s = self.get(owner, id)
        self._publish(s, {'type':'closed', 'message':'Terminal closed by the operator.'})
        asyncio.get_running_loop().remove_reader(s.master)
        # Shell pipelines may use separate process groups, but share the session ID.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in self._session_pids(s.process.pid):
                try: os.kill(pid, sig)
                except ProcessLookupError: pass
            if sig == signal.SIGTERM:
                try: await asyncio.wait_for(asyncio.shield(s.process.wait()), .5)
                except asyncio.TimeoutError: pass
        try: os.close(s.master)
        except OSError: pass
        await s.process.wait()
        if s.watcher: await s.watcher
        self.sessions.pop(id, None)
        self.store.event(owner, 'terminal-closed', id)

    async def reap(self):
        while True:
            await asyncio.sleep(30)
            for s in list(self.sessions.values()):
                if not s.subscribers and time.time() - s.detached_at > 3600:
                    await self.close(s.owner, s.id)

    async def shutdown(self):
        if self.reaper:
            self.reaper.cancel()
            await asyncio.gather(self.reaper, return_exceptions=True)
        for s in list(self.sessions.values()):
            await self.close(s.owner, s.id)
