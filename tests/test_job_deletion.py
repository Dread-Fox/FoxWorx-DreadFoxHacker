"""Finished-job deletion removes only owned captured logs and records."""
import asyncio
import io
import json
import zipfile

import pytest
from fastapi import HTTPException

from test_jobs import manager, proposal, finished
from test_api import client, logged
from foxworx.operation_graph import InvestigationGraph


async def test_delete_finished_manual_job_removes_record_logs_and_export_entry(manager, engagement):
    owner = 'local-operator'
    prepared = proposal(manager, engagement, 'print("deletion-test")')
    job = await manager.approve(owner, prepared['id'], prepared['digest'], True)
    await finished(manager, job['id'])
    workspace_file = manager.store.workspace(engagement['id']) / 'keep.txt'
    workspace_file.write_text('Keep workspace evidence')
    assert (manager.directory / job['id'] / 'combined.log').exists()
    result = await manager.delete(owner, job['id'])
    assert result == {'deleted': True, 'id': job['id']}
    assert manager.store.get('job', job['id'], owner) is None
    assert not (manager.directory / job['id']).exists()
    assert workspace_file.read_text() == 'Keep workspace evidence'
    assert manager.store.get('proposal', prepared['id'], owner)['status'] == 'approved'
    assert any(e['action'] == 'job-deleted' for e in manager.store.events(owner))
    assert all(n.get('job_id') != job['id'] for n in InvestigationGraph(manager.store, manager.cfg.state).get(owner, engagement['id'])['nodes'])
    with pytest.raises(HTTPException) as error:
        manager.output(job['id'], owner)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        await manager.approve(owner, prepared['id'], prepared['digest'], True)


@pytest.mark.parametrize('status', ['succeeded', 'failed', 'stopped', 'timed_out', 'output_limit', 'interrupted'])
async def test_delete_all_finished_statuses_even_without_logs(manager, engagement, status):
    job = manager.store.put('job', 'local-operator', {'engagement_id': engagement['id'], 'status': status})
    assert (await manager.delete('local-operator', job['id']))['deleted']


@pytest.mark.parametrize('status', ['queued', 'running', 'stopping', 'unknown'])
async def test_delete_rejects_active_or_unknown_statuses(manager, engagement, status):
    job = manager.store.put('job', 'local-operator', {'engagement_id': engagement['id'], 'status': status})
    with pytest.raises(HTTPException) as error:
        await manager.delete('local-operator', job['id'])
    assert error.value.status_code == 409
    assert manager.store.get('job', job['id'], 'local-operator') is not None


async def test_delete_checks_ownership_before_touching_logs(manager, engagement):
    job = manager.store.put('job', 'alice', {'engagement_id': engagement['id'], 'status': 'succeeded'})
    directory = manager.directory / job['id']
    directory.mkdir()
    (directory / 'combined.log').write_text('Private output')
    with pytest.raises(HTTPException) as error:
        await manager.delete('bob', job['id'])
    assert error.value.status_code == 404
    assert (directory / 'combined.log').read_text() == 'Private output'


async def test_worker_cleanup_must_finish_before_deletion(manager, engagement):
    job = manager.store.put('job', 'local-operator', {'engagement_id': engagement['id'], 'status': 'succeeded'})
    task = asyncio.create_task(asyncio.sleep(0))
    manager.tasks[job['id']] = task
    try:
        with pytest.raises(HTTPException) as error:
            await manager.delete('local-operator', job['id'])
        assert error.value.status_code == 409
    finally:
        await task
        manager.tasks.pop(job['id'])


async def test_active_rabbit_run_protects_finished_job_until_run_stops(manager, engagement):
    owner = 'local-operator'
    job = manager.store.put('job', owner, {'engagement_id': engagement['id'], 'status': 'failed'})
    run = manager.store.put('rabbit', owner, {'engagement_id': engagement['id'], 'status': 'running',
        'steps': [{'number': 1, 'profile': 'http-headers', 'job_id': job['id'], 'status': 'failed'}]})
    with pytest.raises(HTTPException) as error:
        await manager.delete(owner, job['id'])
    assert error.value.status_code == 409
    run['status'] = 'stopped'
    manager.store.put('rabbit', owner, run)
    await manager.delete(owner, job['id'])
    saved = manager.store.get('rabbit', run['id'], owner)
    assert saved['steps'][0]['job_deleted'] is True
    assert saved['steps'][0]['job_id'] == job['id']
    graph = InvestigationGraph(manager.store, manager.cfg.state).get(owner, engagement['id'])
    assert any(n['kind'] == 'step' for n in graph['nodes'])
    assert all(n['kind'] != 'job' for n in graph['nodes'])


async def test_job_log_symlinks_are_unlinked_without_following_target(manager, engagement, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep.txt').write_text('Keep this')
    job = manager.store.put('job', 'local-operator', {'engagement_id': engagement['id'], 'status': 'succeeded'})
    (manager.directory / job['id']).symlink_to(outside, target_is_directory=True)
    await manager.delete('local-operator', job['id'])
    assert (outside / 'keep.txt').read_text() == 'Keep this'
    assert not (manager.directory / job['id']).is_symlink()


async def test_symlinked_jobs_root_cannot_redirect_deletion(manager, engagement, tmp_path):
    job = manager.store.put('job', 'local-operator', {'engagement_id': engagement['id'], 'status': 'succeeded'})
    outside = tmp_path / 'outside' / job['id']
    outside.mkdir(parents=True)
    (outside / 'keep.txt').write_text('Keep this')
    manager.directory.rmdir()
    manager.directory.symlink_to(outside.parent, target_is_directory=True)
    with pytest.raises(HTTPException) as error:
        await manager.delete('local-operator', job['id'])
    assert error.value.status_code == 500
    assert (outside / 'keep.txt').read_text() == 'Keep this'
    assert manager.store.get('job', job['id'], 'local-operator') is not None


async def test_nested_log_symlink_does_not_remove_external_file(manager, engagement, tmp_path):
    job = manager.store.put('job', 'local-operator', {'engagement_id': engagement['id'], 'status': 'succeeded'})
    directory = manager.directory / job['id']
    directory.mkdir()
    outside = tmp_path / 'keep.txt'
    outside.write_text('Keep this')
    (directory / 'stdout.log').symlink_to(outside)
    await manager.delete('local-operator', job['id'])
    assert outside.read_text() == 'Keep this' and not directory.exists()


async def test_filesystem_error_retains_job_record_for_retry(manager, engagement, monkeypatch):
    job = manager.store.put('job', 'local-operator', {'engagement_id': engagement['id'], 'status': 'succeeded'})
    (manager.directory / job['id']).mkdir()
    def failed_remove(*args, **kwargs):
        raise PermissionError('A private path must not appear in HTTP errors')
    monkeypatch.setattr('foxworx.jobs.shutil.rmtree', failed_remove)
    with pytest.raises(HTTPException) as error:
        await manager.delete('local-operator', job['id'])
    assert error.value.status_code == 500
    assert 'private path' not in error.value.detail
    assert manager.store.get('job', job['id'], 'local-operator') is not None


def test_delete_job_http_requires_csrf_and_removes_evidence(logged):
    app = logged.app
    eid = logged.get('/api/engagements').json()[0]['id']
    job = app.state.store.put('job', 'local-operator', {'engagement_id': eid, 'status': 'succeeded', 'tool': 'curl'})
    directory = app.state.jobs.directory / job['id']
    directory.mkdir()
    (directory / 'combined.log').write_text('Captured log')
    route = '/api/jobs/' + job['id']
    assert logged.request('DELETE', route, json={}, headers={'X-Foxworx-CSRF': ''}).status_code == 403
    assert logged.request('DELETE', route, json={}, headers={'Origin': 'https://untrusted.example'}).status_code == 403
    assert app.state.store.get('job', job['id'], 'local-operator') is not None
    response = logged.request('DELETE', route, json={})
    assert response.status_code == 200 and response.json()['deleted']
    assert logged.get('/api/jobs?engagement_id=' + eid).json() == []
    assert logged.get(route + '/output').status_code == 404
    assert logged.request('DELETE', route, json={}).status_code == 404
    bundle = logged.get('/api/engagements/' + eid + '/export')
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert all(job['id'] not in name for name in archive.namelist())
        assert all(item['id'] != job['id'] for item in json.loads(archive.read('jobs.json')))
