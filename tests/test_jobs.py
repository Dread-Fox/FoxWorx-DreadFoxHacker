import asyncio
import json
import pytest
from fastapi import HTTPException
from foxworx.registry import Registry
from foxworx.jobs import JobManager
from foxworx.models import ProposalSpec

@pytest.fixture
def manager(cfg, store):
    return JobManager(cfg, store, Registry(cfg))

def proposal(manager, engagement, code="print('hello')"):
    return manager.prepare('local-operator', ProposalSpec(engagement_id=engagement['id'], tool='python3', args=['-c', code]))

async def finished(manager, id):
    for _ in range(200):
        record = manager.store.get('job', id, 'local-operator')
        if record['status'] not in ['queued', 'running', 'stopping']:
            return record
        await asyncio.sleep(.025)
    raise AssertionError('Job did not finish')

@pytest.mark.asyncio
async def test_approval_is_required_and_cannot_be_replayed(manager, engagement):
    p = proposal(manager, engagement)
    with pytest.raises(HTTPException):
        await manager.approve('local-operator', p['id'], p['digest'], False)
    j = await manager.approve('local-operator', p['id'], p['digest'], True)
    with pytest.raises(HTTPException):
        await manager.approve('local-operator', p['id'], p['digest'], True)
    result = await finished(manager, j['id'])
    assert result['status'] == 'succeeded'
    assert 'hello' in manager.output(j['id'], 'local-operator')['text']

@pytest.mark.asyncio
async def test_wrong_owner_cannot_approve_or_read(manager, engagement):
    p = proposal(manager, engagement)
    with pytest.raises(HTTPException):
        await manager.approve('other@example.test', p['id'], p['digest'], True)
    with pytest.raises(HTTPException):
        manager.output('a'*24, 'other@example.test')

@pytest.mark.asyncio
async def test_nonzero_exit_is_failed_not_finished(manager, engagement):
    p = proposal(manager, engagement, 'import sys; print("problem",file=sys.stderr); sys.exit(3)')
    j = await manager.approve('local-operator', p['id'], p['digest'], True)
    r = await finished(manager, j['id'])
    assert r['status'] == 'failed' and r['returncode'] == 3
    assert 'problem' in manager.output(j['id'], 'local-operator')['text']

@pytest.mark.asyncio
async def test_stop_escalates_and_records_stopped(manager, engagement):
    p = proposal(manager, engagement, 'import time; print("start",flush=True); time.sleep(30)')
    j = await manager.approve('local-operator', p['id'], p['digest'], True)
    await asyncio.sleep(.1)
    await manager.stop('local-operator', j['id'])
    assert (await finished(manager, j['id']))['status'] == 'stopped'

@pytest.mark.asyncio
async def test_output_limit_stops_run(manager, engagement):
    manager.cfg.log_bytes = 1024
    p = proposal(manager, engagement, 'print("X"*100000)')
    j = await manager.approve('local-operator', p['id'], p['digest'], True)
    assert (await finished(manager, j['id']))['status'] == 'output_limit'
    assert len(manager.output(j['id'], 'local-operator')['text'].encode()) <= 1024

def test_scope_blocked_before_binary_lookup(manager, engagement):
    with pytest.raises(HTTPException) as e:
        manager.prepare('local-operator', ProposalSpec(engagement_id=engagement['id'], tool='nmap', profile='tcp-connect', target='192.0.2.1'))
    assert e.value.status_code == 403

def test_unknown_tool_rejected(manager, engagement):
    with pytest.raises(HTTPException):
        manager.prepare('local-operator', ProposalSpec(engagement_id=engagement['id'], tool='definitely-not-installed'))

@pytest.mark.asyncio
async def test_updated_authorization_notes_invalidate_proposal(manager,engagement):
    p=proposal(manager,engagement)
    updated={**engagement,'notes':'New program restriction: no automated scanning'}
    manager.store.put('engagement','local-operator',updated)
    with pytest.raises(HTTPException) as e:
        await manager.approve('local-operator',p['id'],p['digest'],True)
    assert e.value.status_code==409

@pytest.mark.asyncio
async def test_expired_or_changed_digest_not_executable(manager,engagement):
    import time
    p=proposal(manager,engagement)
    with pytest.raises(HTTPException): await manager.approve('local-operator',p['id'],'x'*64,True)
    p['expires']=time.time()-1;manager.store.put('proposal','local-operator',p)
    with pytest.raises(HTTPException): await manager.approve('local-operator',p['id'],p['digest'],True)
    assert not manager.tasks

@pytest.mark.asyncio
async def test_timeout_is_distinct_from_success(manager,engagement):
    manager.cfg.job_timeout=.1
    p=proposal(manager,engagement,'import time; time.sleep(20)')
    j=await manager.approve('local-operator',p['id'],p['digest'],True)
    assert (await finished(manager,j['id']))['status']=='timed_out'

@pytest.mark.asyncio
async def test_concurrency_limit_does_not_consume_rejected_proposal(manager,engagement):
    manager.cfg.max_jobs=1
    p=proposal(manager,engagement,'import time; time.sleep(20)')
    p2=proposal(manager,engagement)
    j=await manager.approve('local-operator',p['id'],p['digest'],True)
    with pytest.raises(HTTPException) as e:
        await manager.approve('local-operator',p2['id'],p2['digest'],True)
    assert e.value.status_code==429
    assert manager.store.get('proposal',p2['id'],'local-operator')['status']=='pending'
    await manager.stop('local-operator',j['id']);await finished(manager,j['id'])

def test_restart_does_not_repeat_jobs(manager,engagement):
    j=manager.store.put('job','local-operator',{'engagement_id':engagement['id'],'status':'running'})
    manager.recover()
    assert manager.store.get('job',j['id'],'local-operator')['status']=='interrupted'
    assert not manager.tasks

def test_utf8_output_boundary_preserves_characters(manager,engagement):
    j=manager.store.put('job','local-operator',{'engagement_id':engagement['id'],'status':'succeeded'})
    directory=manager.directory/j['id'];directory.mkdir()
    expected='a'*65535+'€ end'
    (directory/'combined.log').write_bytes(expected.encode())
    first=manager.output(j['id'],'local-operator')
    second=manager.output(j['id'],'local-operator',first['offset'])
    assert first['text']+second['text']==expected
