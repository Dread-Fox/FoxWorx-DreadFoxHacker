"""DreadFox companion: small, deterministic, opt-in game state.

This module deliberately has no access to terminals, model clients, job payloads,
network interfaces, or command output.  Audit *action names* only are admitted.
No raw audit details are ever copied into pet memory.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import json
import logging
import math
import secrets
import time
from typing import Callable

LOG = logging.getLogger(__name__)
MAX_DAILY_XP = 120
MAX_MEMORIES = 80
RECENT_MEMORIES = 30
# Strict internal event-to-category map. Never copy audit details, tool names,
# hostnames, target addresses, output, file names, or operator-provided strings.
OPS_CATEGORIES = {
    'terminal-created': 'terminal_sessions',
    'job-approved': 'reviewed_jobs',
    'job-succeeded': 'completed_jobs',
    'job-failed': 'unfinished_jobs',
    'job-stopped': 'unfinished_jobs',
    'job-timed_out': 'unfinished_jobs',
    'job-interrupted': 'unfinished_jobs',
    'job-output_limit': 'unfinished_jobs',
    'ai-request': 'learning_sessions',
    'engagement-created': 'workspace_planning',
    'engagement-updated': 'workspace_planning',
    'file-uploaded': 'evidence_organization',
    'evidence-exported': 'evidence_organization',
}
OPS_DAYS = 7
OPS_MAX_COUNT = 20


def _activity_band(count: int) -> str:
    if count < 2: return 'some'
    if count < 5: return 'a_few'
    if count < 10: return 'several'
    return 'frequent'


# category, XP, per-event cooldown seconds, safe one-sentence diary description
ACTIVITIES = {
    'terminal-created': ('exploration', 3, 180, 'Opened a new path through the workshop.'),
    'job-succeeded': ('craft', 12, 60, 'Completed a workbench task together.'),
    'job-approved': ('stewardship', 3, 180, 'Practiced deliberate, reviewed tool use.'),
    'ai-request': ('wisdom', 5, 240, 'Spent time learning with a copilot.'),
    'engagement-created': ('exploration', 8, 300, 'Prepared a new authorized workspace.'),
    'engagement-updated': ('stewardship', 3, 300, 'Maintained the workspace plan.'),
    'evidence-exported': ('stewardship', 10, 300, 'Organized and preserved project evidence.'),
    'file-uploaded': ('craft', 5, 300, 'Added an artifact to a workspace.'),
}
STAGES = (
    ('Fox Kit', 1, 0, 0),
    ('Curious Scout', 2, 1, 50),
    ('Clever Trickster', 3, 3, 120),
    ('Forest Guardian', 4, 7, 250),
    ('Arcane Sage', 5, 14, 450),
    ('Moonlit Mystic', 6, 30, 800),
    ('Silver Elder', 7, 90, 1400),
    ('Starbound Spirit', 8, 180, 2200),
    ('Nine-Tailed Guardian', 9, 365, 3500),
)
CARE = {
    'play': {'cooldown': 1800, 'energy': -7, 'bond': 4, 'curiosity': 4, 'note': 'Played together beneath the stars.'},
    'feed': {'cooldown': 3600, 'energy': 12, 'bond': 2, 'curiosity': 0, 'note': 'Shared a virtual snack.'},
    'rest': {'cooldown': 7200, 'energy': 18, 'bond': 1, 'curiosity': 0, 'note': 'Took a peaceful pause.'},
}


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec='seconds')


def _bounded(value: int) -> int:
    return max(0, min(100, value))


def _profile(name: str, at: float) -> dict:
    return {'id': secrets.token_hex(12), 'name': name, 'created_at': _utc(at),
            'last_active_at': _utc(at), 'last_changed_at': _utc(at), 'tracking': True,
            'xp': 0, 'energy': 65, 'bond': 45, 'curiosity': 50,
            'counts': {x: 0 for x in ('exploration','craft','wisdom','stewardship')},
            'awards': {}, 'daily_date': '', 'daily_xp': 0, 'streak': 0,
            'last_streak_day': '', 'longest_streak': 0, 'last_care': {},
            'chat_mode':'offline', 'focus':'auto', 'ops_context':False}


def _epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


class DreadFoxPet:
    """Owns pet-specific SQLite tables and an independent bounded event queue.

    The audit sink is a nonblocking observer. No pet failure can block a
    terminal, managed job, or ordinary audit record from being committed.
    """
    def __init__(self, store, *, clock: Callable[[], float] = time.time):
        self.store = store
        self.clock = clock
        self.queue: asyncio.Queue | None = None
        self.worker: asyncio.Task | None = None
        self.dropped = 0
        with store.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS pet_profiles (
                  owner TEXT PRIMARY KEY, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pet_memories (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  owner TEXT NOT NULL, at TEXT NOT NULL,
                  kind TEXT NOT NULL, note TEXT NOT NULL, xp INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS pet_memory_owner ON pet_memories(owner,id);
                CREATE TABLE IF NOT EXISTS pet_operation_days (
                  owner TEXT NOT NULL, pet_id TEXT NOT NULL, day TEXT NOT NULL,
                  area TEXT NOT NULL, count INTEGER NOT NULL,
                  PRIMARY KEY(owner,pet_id,day,area)
                );
            ''')
            rows = db.execute('SELECT owner,data FROM pet_profiles').fetchall()
        self.active = {r['owner']: json.loads(r['data'])['id'] for r in rows
                       if json.loads(r['data']).get('tracking', False)}

    def start(self):
        if self.worker is not None:
            return
        self.queue = asyncio.Queue(maxsize=1024)
        self.worker = asyncio.create_task(self._run(), name='dreadfox-pet-observer')
        self.store.pet_observer = self.observe

    async def stop(self):
        self.store.pet_observer = None
        if self.queue is not None and self.worker is not None:
            try:
                await asyncio.wait_for(self.queue.join(), timeout=3)
            except asyncio.TimeoutError:
                LOG.warning('DreadFox observer shutdown skipped queued events')
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        self.worker = None
        self.queue = None

    async def _run(self):
        assert self.queue is not None
        while True:
            owner, kind, when, generation = await self.queue.get()
            try:
                await asyncio.to_thread(self.process_event,owner,kind,when,expected_id=generation)
            except Exception:  # an optional pet should never disrupt the workbench
                LOG.exception('DreadFox background observer failed')
            finally:
                self.queue.task_done()

    def observe(self, owner: str, kind: str, details: str = '') -> bool:
        """Only dispatch bounded generic action names. Never store/copy details."""
        if kind not in OPS_CATEGORIES or owner not in self.active or self.queue is None:
            return False
        try:
            self.queue.put_nowait((owner,kind,self.clock(),self.active[owner]))
        except asyncio.QueueFull:
            self.dropped += 1
            return False
        return True

    def _load(self, db, owner: str) -> dict | None:
        row = db.execute('SELECT data FROM pet_profiles WHERE owner=?',(owner,)).fetchone()
        return json.loads(row['data']) if row else None

    def _save(self, db, owner: str, pet: dict):
        db.execute('INSERT INTO pet_profiles(owner,data) VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET data=excluded.data',
                   (owner,json.dumps(pet,ensure_ascii=False,separators=(',',':'))))

    def _memory(self, db, owner: str, when: float, kind: str, note: str, xp: int = 0):
        # Only static built-in narration may be passed here, never arbitrary user text.
        db.execute('INSERT INTO pet_memories(owner,at,kind,note,xp) VALUES(?,?,?,?,?)',
                   (owner,_utc(when),kind,note,xp))
        db.execute('DELETE FROM pet_memories WHERE owner=? AND id NOT IN '
                   '(SELECT id FROM pet_memories WHERE owner=? ORDER BY id DESC LIMIT ?)',
                   (owner,owner,MAX_MEMORIES))

    def hatch(self, owner: str) -> dict:
        at=self.clock()
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            pet=self._load(db,owner)
            if pet is None:
                pet=_profile('DreadFox',at)
                self._save(db,owner,pet)
                self._memory(db,owner,at,'hatch','A little fox spirit hatched into your workbench.')
        if pet.get('tracking'):
            self.active[owner]=pet['id']
        return self.snapshot(owner)

    def process_event(self, owner: str, kind: str, at: float | None = None,
                      *, details: str = '', expected_id: str | None = None) -> bool:
        """Trusted internal event only, never accepts action kind from HTTP.

        The details argument is deliberately ignored, including for storage.
        A transaction makes cooldowns and daily XP limits atomic.
        """
        if kind not in OPS_CATEGORIES:
            return False
        when=at if at is not None else self.clock()
        reward=ACTIVITIES.get(kind)
        day=_utc(when)[:10]
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            p=self._load(db,owner)
            if not p or not p['tracking'] or (expected_id and p['id'] != expected_id):
                return False
            if p.get('ops_context',False):
                self._record_operation(db,owner,p['id'],kind,when)
            if reward is None:  # observation is not a reward for failed jobs
                return False
            category, award, cooldown, note=reward
            if when-float(p.get('awards',{}).get(kind,0)) < cooldown:
                return False
            earned=p['daily_xp'] if p['daily_date']==day else 0
            credit=min(award, max(0,MAX_DAILY_XP-earned))
            if not credit:
                return False
            p['daily_date'],p['daily_xp']=day,earned+credit
            p['awards'][kind]=when
            p['xp']+=credit
            p['counts'][category]+=1
            p['last_active_at']=_utc(when)
            p['energy']=_bounded(self._rested_energy(p,when)-2)
            p['bond']=_bounded(p['bond']+1)
            p['curiosity']=_bounded(p['curiosity']+1 if category in ('exploration','wisdom') else p['curiosity'])
            if day!=p['last_streak_day']:
                prior=p['last_streak_day']
                p['streak']=p['streak']+1 if prior and (datetime.fromisoformat(day).date()-datetime.fromisoformat(prior).date()).days==1 else 1
                p['last_streak_day']=day
                p['longest_streak']=max(p.get('longest_streak',0),p['streak'])
            p['last_changed_at']=_utc(when)
            self._save(db,owner,p)
            self._memory(db,owner,when,category,note,credit)
        return True

    @staticmethod
    def _record_operation(db, owner: str, pet_id: str, kind: str, when: float):
        # Aggregate entirely inside the owner-scoped transaction. Nothing from
        # audit.details enters this function; counts saturate, dates are UTC.
        day = _utc(when)[:10]
        area = OPS_CATEGORIES[kind]
        db.execute('''INSERT INTO pet_operation_days(owner,pet_id,day,area,count)
            VALUES(?,?,?,?,1) ON CONFLICT(owner,pet_id,day,area)
            DO UPDATE SET count=MIN(?,count+1)''',
            (owner,pet_id,day,area,OPS_MAX_COUNT))
        first_day=(datetime.fromtimestamp(when,timezone.utc).date()-timedelta(days=OPS_DAYS-1)).isoformat()
        db.execute('DELETE FROM pet_operation_days WHERE owner=? AND (pet_id<>? OR day<?)',
                   (owner,pet_id,first_day))

    def operations(self,owner: str,at: float | None = None) -> dict:
        """Only sanitized, short-lived aggregated data from explicitly enabled tracking."""
        when=self.clock() if at is None else at
        first=(datetime.fromtimestamp(when,timezone.utc).date()-timedelta(days=OPS_DAYS-1)).isoformat()
        last=_utc(when)[:10]
        with self.store.db() as db:
            p=self._load(db,owner)
            if not p: return {'hatched':False,'enabled':False,'tracking':False,'window_days':OPS_DAYS,'signals':[]}
            db.execute('DELETE FROM pet_operation_days WHERE owner=? AND (pet_id<>? OR day<?)',
                       (owner,p['id'],first))
            enabled=bool(p.get('ops_context',False))
            tracking=bool(p.get('tracking',False))
            if not enabled or not tracking:
                rows=[]
            else:
                rows=db.execute('''SELECT area,SUM(count) AS total FROM pet_operation_days
                    WHERE owner=? AND pet_id=? AND day BETWEEN ? AND ?
                    GROUP BY area ORDER BY area''',(owner,p['id'],first,last)).fetchall()
        return {'hatched':True,'enabled':enabled,'tracking':tracking,'window_days':OPS_DAYS,
                'signals':[{'area':r['area'],'level':_activity_band(r['total'])} for r in rows]}

    def set_operations(self,owner: str,enabled: bool) -> dict:
        """Separate opt-in from XP; turning OFF erases saved pulse immediately."""
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            p=self._load(db,owner)
            if not p: raise ValueError('Hatch your DreadFox first')
            if p.get('ops_context',False) != bool(enabled):
                # Fresh epoch prevents previously contextualized AI chat from
                # being re-forwarded after a privacy preference change.
                p['ops_epoch']=secrets.token_hex(12)
            p['ops_context']=bool(enabled)
            self._save(db,owner,p)
            if not enabled:
                db.execute('DELETE FROM pet_operation_days WHERE owner=?',(owner,))
        return self.operations(owner)

    def clear_operations(self,owner: str) -> dict:
        return self.set_operations(owner,False)

    @staticmethod
    def _rested_energy(p: dict, at: float) -> int:
        elapsed=max(0, at - _epoch(p['last_changed_at']))
        # Rest slowly regenerates energy; extended inactivity is not punished.
        return _bounded(int(p['energy'])+int(elapsed//3600)*2)

    def care(self,owner: str,action: str) -> dict:
        if action not in CARE:
            raise ValueError('Unknown care action')
        at=self.clock()
        rule=CARE[action]
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            p=self._load(db,owner)
            if not p:
                raise ValueError('Hatch your DreadFox first')
            remain=int(rule['cooldown'] - (at-float(p['last_care'].get(action,0))))
            if remain>0:
                raise ValueError(f'Care cooldown: try again in {math.ceil(remain/60)} minute(s)')
            p['energy']=_bounded(self._rested_energy(p,at)+rule['energy'])
            p['bond']=_bounded(p['bond']+rule['bond'])
            p['curiosity']=_bounded(p['curiosity']+rule['curiosity'])
            p['last_care'][action]=at
            p['last_changed_at']=_utc(at)
            self._save(db,owner,p)
            self._memory(db,owner,at,'care',rule['note'])
        return self.snapshot(owner)

    def rename(self,owner: str,name: str) -> dict:
        name=' '.join(name.split())
        if not 1<=len(name)<=24 or not all(c.isalnum() or c in ' -\u2019\'' for c in name):
            raise ValueError('Name must be 1–24 letters, numbers, spaces, apostrophes or hyphens')
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            p=self._load(db,owner)
            if p is None: raise ValueError('Hatch your DreadFox first')
            p['name']=name
            self._save(db,owner,p)
        return self.snapshot(owner)

    def tracking(self,owner: str, enabled: bool) -> dict:
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            p=self._load(db,owner)
            if p is None: raise ValueError('Hatch your DreadFox first')
            p['tracking']=bool(enabled)
            self._save(db,owner,p)
        if enabled: self.active[owner]=p['id']
        else: self.active.pop(owner,None)
        return self.snapshot(owner)

    def delete(self,owner: str):
        self.active.pop(owner,None)
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM pet_profiles WHERE owner=?',(owner,))
            db.execute('DELETE FROM pet_memories WHERE owner=?',(owner,))
            db.execute('DELETE FROM pet_operation_days WHERE owner=?',(owner,))
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pet_conversations'").fetchone():
                db.execute('DELETE FROM pet_conversations WHERE owner=?',(owner,))

    def snapshot(self, owner: str, at: float | None = None) -> dict:
        when=at if at is not None else self.clock()
        with self.store.db() as db:
            p=self._load(db,owner)
            if p is None:
                return {'hatched':False,'tracking':False,'name':'DreadFox', 'message':'Hatch a fox spirit when you are ready. No pet activity is recorded before hatching.'}
            memories=db.execute('SELECT at,kind,note,xp FROM pet_memories WHERE owner=? ORDER BY id DESC LIMIT ?',
                                (owner,RECENT_MEMORIES)).fetchall()
        age_days=max(0,int((when-_epoch(p['created_at']))//86400))
        stage,tails,_,_=max((s for s in STAGES if age_days>=s[2] and p['xp']>=s[3]),key=lambda x:x[1])
        level=min(99,math.isqrt(p['xp']//20)+1)
        energy=self._rested_energy(p,when)
        idle=max(0,when-_epoch(p['last_active_at']))
        if idle>24*3600: mood='Dreaming'
        elif energy<25: mood='Sleepy'
        elif p['bond']>=75 and idle<4*3600: mood='Delighted'
        elif p['curiosity']>=75: mood='Inquisitive'
        else: mood='Content'
        date=_utc(when)[:10]
        next_care={kind:max(0,round(rule['cooldown']-(when-float(p['last_care'].get(kind,0))))) for kind,rule in CARE.items()}
        badges=[]
        if p['xp']>=1: badges.append({'icon':'✧','name':'First Spark','detail':'Earned the first workbench experience.'})
        if p['counts']['craft']>=10: badges.append({'icon':'⚒','name':'Craft Companion','detail':'Ten recorded successful workbench activities.'})
        if p['counts']['wisdom']>=10: badges.append({'icon':'✦','name':'Curious Mind','detail':'Ten learning sessions together.'})
        if p['counts']['stewardship']>=10: badges.append({'icon':'◇','name':'Careful Keeper','detail':'Ten planning and evidence activities.'})
        if p.get('longest_streak',p['streak'])>=7: badges.append({'icon':'☼','name':'Seven Sunrises','detail':'Seven consecutive active UTC days.'})
        if tails>=3: badges.append({'icon':'☾','name':'The Third Tail','detail':'A fox spirit has begun to grow.'})
        return {'hatched':True,'tracking':p['tracking'],'name':p['name'], 'created_at':p['created_at'],
                'stage':stage,'tails':tails,'age_days':age_days,'level':level,'xp':p['xp'],
                'xp_level_start':20*(level-1)**2, 'xp_next':20*level**2,
                'energy':energy, 'bond':p['bond'], 'curiosity':p['curiosity'],
                'mood':mood,'streak_days':p['streak'], 'activity':p['counts'],
                'today_xp':p['daily_xp'] if p['daily_date']==date else 0,
                'daily_cap':MAX_DAILY_XP,'next_care':next_care,'badges':badges,
                'memories':[dict(r) for r in memories],
                'next_tail':next(({'tails':s[1],'days':s[2],'xp':s[3]} for s in STAGES if s[1]>tails),None),
                'message':'Taking a break from activity tracking.' if not p['tracking'] else
                          'Growing alongside your work, one good habit at a time.'}
