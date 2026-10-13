"""DreadFox pet must never be able to execute or observe sensitive work data."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from foxworx.app import create_app
from foxworx.pet import DreadFoxPet


def test_pet_opt_in_and_no_unhatched_tracking(store):
    pet = DreadFoxPet(store)
    assert pet.snapshot('alice')['hatched'] is False
    assert pet.observe('alice','job-succeeded') is False
    assert pet.snapshot('alice')['hatched'] is False
    first = pet.hatch('alice')
    assert first['hatched'] and first['xp'] == 0 and first['tails'] == 1
    assert first['name'] == 'DreadFox'
    assert pet.snapshot('bob')['hatched'] is False


def test_activity_is_coarse_private_and_bounded(store):
    pet = DreadFoxPet(store)
    pet.hatch('alice')
    stamp=1_800_000_000
    assert pet.process_event('alice','job-succeeded',at=stamp, details='SECRET-TARGET user-password')
    assert not pet.process_event('alice','job-succeeded',at=stamp+2, details='SECRET-TARGET')
    assert not pet.process_event('alice','irrelevant-action',at=stamp+200, details='SECRET-TARGET')
    for n in range(200):
        pet.process_event('alice','job-succeeded',at=stamp+61*(n+1),details='SECRET-TARGET')
    view=pet.snapshot('alice',at=stamp+61*201)
    assert 0 < view['xp'] <= 120
    assert view['activity']['craft'] > 0
    assert 'SECRET-TARGET' not in json.dumps(view)
    with store.db() as db:
        entries=db.execute('SELECT * FROM pet_memories').fetchall()
        profiles=db.execute('SELECT * FROM pet_profiles').fetchall()
    assert 'SECRET-TARGET' not in str([dict(x) for x in entries+profiles])


def test_growth_depends_on_xp_and_elapsed_time(store):
    pet=DreadFoxPet(store)
    pet.hatch('alice')
    now=datetime.now(timezone.utc)
    with store.db() as db:
        data=json.loads(db.execute('SELECT data FROM pet_profiles WHERE owner=?',('alice',)).fetchone()[0])
        data['created_at']=(now-timedelta(days=410)).isoformat()
        data['xp']=5200
        db.execute('UPDATE pet_profiles SET data=? WHERE owner=?',(json.dumps(data),'alice'))
    snap=pet.snapshot('alice')
    assert snap['tails']==9 and snap['stage']=='Nine-Tailed Guardian'
    assert snap['level']>1 and snap['xp_next']>snap['xp']


def test_care_pausing_renaming_and_delete(store):
    pet=DreadFoxPet(store); pet.hatch('alice')
    old=pet.snapshot('alice')['xp']
    result=pet.care('alice','play')
    assert result['bond']>45 and result['xp']==old
    with pytest.raises(ValueError,match='cooldown'):
        pet.care('alice','play')
    with pytest.raises(ValueError):
        pet.rename('alice','<img src=x onerror=alert(1)>')
    assert pet.rename('alice','Kitsu')['name']=='Kitsu'
    pet.tracking('alice',False)
    assert pet.observe('alice','job-succeeded') is False
    assert pet.process_event('alice','job-succeeded') is False
    assert pet.snapshot('alice')['tracking'] is False
    pet.delete('alice')
    assert pet.snapshot('alice')['hatched'] is False
    assert pet.snapshot('bob')['hatched'] is False


def test_memory_log_is_bounded_and_generic(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    stamp=1_800_000_000
    for n in range(100):
        pet.process_event('alice','engagement-created',at=stamp+n*700)
    snap=pet.snapshot('alice',at=stamp+100*700)
    assert len(snap['memories'])<=30
    assert all(set(item) == {'at','kind','note','xp'} for item in snap['memories'])


@pytest.fixture
def petclient(cfg):
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as c:
        assert c.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        info=c.get('/api/session').json()
        c.headers.update({'Origin':cfg.origin,'X-Foxworx-CSRF':info['csrf']})
        yield c


def test_pet_api_authorization_isolation_and_no_ai_dependency(petclient):
    client=petclient
    assert client.get('/api/pet').json()['hatched'] is False
    assert client.post('/api/pet/hatch',json={}).json()['hatched']
    assert client.put('/api/pet/name',json={'name':'Shadow Fox'}).json()['name']=='Shadow Fox'
    assert client.post('/api/pet/care',json={'action':'feed'}).status_code==200
    assert client.put('/api/pet/tracking',json={'enabled':False}).json()['tracking'] is False
    assert client.get('/api/pet').json()['name']=='Shadow Fox'
    assert client.request('DELETE','/api/pet',json={}).status_code==200
    assert client.get('/api/pet').json()['hatched'] is False
    assert client.post('/api/pet/hatch',json={},headers={'X-Foxworx-CSRF':'bad'}).status_code==403


def test_pet_observer_queue_tracks_existing_audit_without_blocking(petclient):
    c=petclient
    c.post('/api/pet/hatch',json={})
    eng=c.get('/api/engagements').json()[0]['id']
    res=c.post('/api/engagements',json={'name':'Second local lab','include':['localhost'],'exclude':[]})
    assert res.status_code==200
    # The real app's audit observer must deliver asynchronously to pet, not on request path.
    import time
    for _ in range(100):
        snap=c.get('/api/pet').json()
        if snap['xp']>0: break
        time.sleep(.01)
    assert snap['xp']>0
    with c.app.state.store.db() as db:
        assert db.execute('SELECT COUNT(*) FROM pet_profiles').fetchone()[0]==1


def test_two_operators_are_separate_across_restart(store):
    first=DreadFoxPet(store)
    first.hatch('operator-one')
    first.hatch('operator-two')
    first.rename('operator-one','Ember')
    first.process_event('operator-one','job-succeeded')
    first.process_event('operator-two','evidence-exported')
    second=DreadFoxPet(store)
    one=second.snapshot('operator-one')
    two=second.snapshot('operator-two')
    assert one['name']=='Ember'
    assert two['name']=='DreadFox'
    assert one['activity']['craft']==1 and two['activity']['craft']==0
    assert two['activity']['stewardship']==1 and one['activity']['stewardship']==0
    second.delete('operator-one')
    assert second.snapshot('operator-one')['hatched'] is False
    assert second.snapshot('operator-two')['hatched'] is True


def test_old_queued_events_are_not_replayed_after_reset(store):
    pet=DreadFoxPet(store)
    pet.hatch('alice')
    old_id=pet.active['alice']
    pet.delete('alice')
    pet.hatch('alice')
    assert not pet.process_event('alice','job-succeeded',expected_id=old_id)
    assert pet.snapshot('alice')['xp']==0


def test_very_long_absence_does_not_destroy_progress_or_pet(store):
    clock=[1_800_000_000.0]
    pet=DreadFoxPet(store,clock=lambda:clock[0])
    pet.hatch('alice')
    pet.care('alice','play')
    initial=pet.snapshot('alice')
    clock[0] += 86400*365*3
    after=pet.snapshot('alice')
    assert after['hatched']
    assert after['energy']==100
    assert after['xp']==initial['xp']
    assert after['mood']=='Dreaming'
    assert after['next_care']['play']==0


def test_paused_pet_remains_paused_after_restarting(store):
    pet=DreadFoxPet(store);pet.hatch('alice')
    pet.tracking('alice',False)
    recovered=DreadFoxPet(store)
    assert 'alice' not in recovered.active
    assert recovered.snapshot('alice')['hatched'] is True
    assert recovered.snapshot('alice')['tracking'] is False


def test_pet_api_denies_unauthenticated_and_cross_origin_requests(cfg):
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as c:
        assert c.get('/api/pet').status_code==401
        assert c.post('/api/pet/hatch',json={}).status_code==401
        assert c.request('DELETE','/api/pet',json={}).status_code==401
        assert c.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        assert c.post('/api/pet/hatch',json={},headers={'Origin':'https://bad.example'}).status_code==403


def test_milestone_keepsake_survives_a_broken_streak(store):
    clock=[1_800_000_000.0]
    pet=DreadFoxPet(store,clock=lambda:clock[0])
    pet.hatch('alice')
    for _ in range(7):
        assert pet.process_event('alice','terminal-created',at=clock[0])
        clock[0]+=86400
    before=pet.snapshot('alice')
    assert any(b['name']=='Seven Sunrises' for b in before['badges'])
    clock[0]+=86400*8
    pet.process_event('alice','terminal-created',at=clock[0])
    after=pet.snapshot('alice')
    assert after['streak_days']==1
    assert any(b['name']=='Seven Sunrises' for b in after['badges'])


def test_broken_pet_observer_never_breaks_operational_audit(store):
    pet=DreadFoxPet(store)
    pet.hatch('alice')
    def broken(*args):
        raise RuntimeError('optional game broken')
    store.pet_observer=broken
    store.event('alice','job-succeeded','arbitrary operational metadata')
    events=store.events('alice')
    assert len(events)==1
    assert events[0]['details']=='arbitrary operational metadata'
    assert pet.snapshot('alice')['xp']==0


def test_pet_queue_drops_when_full_without_waiting(store):
    pet=DreadFoxPet(store)
    pet.hatch('alice')
    pet.queue=asyncio.Queue(maxsize=1)
    assert pet.observe('alice','job-succeeded')
    assert not pet.observe('alice','job-succeeded')
    assert pet.dropped==1
    assert pet.snapshot('alice')['xp']==0  # queue isn't a synchronous executor


def test_invalid_optional_pet_data_cannot_disable_terminal_service(cfg):
    """Pet storage faults must be isolated from the critical workbench startup."""
    from foxworx.store import Store
    s=Store(cfg.state)
    with s.db() as db:
        db.execute('CREATE TABLE pet_profiles (owner TEXT PRIMARY KEY, data TEXT NOT NULL)')
        db.execute('INSERT INTO pet_profiles VALUES (?,?)',('old-operator','not-json'))
    app=create_app(cfg,_allow_root_for_tests=True)
    with TestClient(app,base_url=cfg.origin,client=('127.0.0.1',50000)) as c:
        assert c.post('/api/login',json={'token':cfg.local_token},headers={'Origin':cfg.origin}).status_code==200
        info=c.get('/api/session').json()
        assert info['version']=='3.3.3'
        assert c.get('/api/tools').status_code==200
        assert c.get('/api/pet').status_code==503
