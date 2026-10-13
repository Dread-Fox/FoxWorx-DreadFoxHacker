import asyncio
import base64
import pytest
from fastapi import HTTPException
from foxworx.terminal import TerminalManager

@pytest.mark.asyncio
async def test_real_pty_and_reconnect(cfg,store,engagement):
    mgr=TerminalManager(cfg,store)
    record=await mgr.create('local-operator',engagement['id'])
    s,q=mgr.attach('local-operator',record['id'])
    try:
        await mgr.write(s,"printf 'FOX-PTY-OK\\n'\n")
        collected=b''
        for _ in range(30):
            msg=await asyncio.wait_for(q.get(),2)
            if msg['type']=='output': collected+=base64.b64decode(msg['data'])
            if b'FOX-PTY-OK\r\n' in collected: break
        assert b'FOX-PTY-OK\r\n' in collected
        mgr.detach(s,q)
        assert s.process.returncode is None
        s2,q2=mgr.attach('local-operator',record['id'])
        assert s2 is s and b'FOX-PTY-OK' in b''.join(s.history)
        with pytest.raises(HTTPException): mgr.get('other',record['id'])
        mgr.detach(s2,q2)
    finally:
        await mgr.close('local-operator',record['id'])
    assert not mgr.sessions
