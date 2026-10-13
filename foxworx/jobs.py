"""Reviewable immutable proposals and bounded, accountable subprocess jobs."""
from __future__ import annotations
import asyncio
import codecs
import hmac
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import shutil
import stat
import time
from urllib.parse import urlsplit
from fastapi import HTTPException
from .config import Settings, child_environment
from .models import ProposalSpec
from .registry import Registry
from .scope import allowed, normalize_target
from .store import Store, identifier, now

ACTIVE = {'queued', 'running', 'stopping'}
FINISHED = {'succeeded', 'failed', 'stopped', 'timed_out', 'output_limit', 'interrupted'}
PROFILES = {
    'tcp-connect': {'tool':'nmap', 'label':'TCP service inventory', 'hint':'One host, 100 common ports; TCP connect, no raw socket privilege.'},
    'http-headers': {'tool':'curl', 'label':'HTTP response headers', 'hint':'One URL; does not follow redirects.'},
    'dns-a': {'tool':'dig', 'label':'DNS A record', 'hint':'One hostname using configured DNS resolvers.'},
    'whois': {'tool':'whois', 'label':'Registration lookup', 'hint':'One name; registry referral services may be contacted.'},
    'tcp-web': {'tool':'nmap', 'label':'Web TCP ports', 'hint':'One host, ports 80/443/8080/8443, low-rate TCP connect.'},
    'http-options': {'tool':'curl', 'label':'HTTP OPTIONS metadata', 'hint':'One URL, OPTIONS request; never follows redirects.'},
    'dns-aaaa': {'tool':'dig', 'label':'DNS AAAA lookup', 'hint':'One hostname using configured DNS resolvers.'},
    'dns-mx': {'tool':'dig', 'label':'DNS MX lookup', 'hint':'One hostname using configured DNS resolvers.'},
    'dns-txt': {'tool':'dig', 'label':'DNS TXT lookup', 'hint':'One hostname using configured DNS resolvers.'},
    'dns-caa': {'tool':'dig', 'label':'DNS CAA policy lookup', 'hint':'One hostname; fixed CAA DNS question.'},
    'dns-ns': {'tool':'dig', 'label':'DNS nameserver lookup', 'hint':'One hostname; fixed NS DNS question.'},
    'dns-soa': {'tool':'dig', 'label':'DNS authority lookup', 'hint':'One hostname; fixed SOA DNS question.'},
    'dns-cname': {'tool':'dig', 'label':'DNS CNAME lookup', 'hint':'One hostname; fixed CNAME DNS question.'},
    'tls-certificate': {'tool':'openssl', 'label':'TLS certificate handshake', 'hint':'One approved hostname/IP, port 443; noninteractive TLS handshake.'},
    'http-status': {'tool':'curl', 'label':'HTTP status and timings', 'hint':'One exact URL; response discarded, no redirects.'},
    'http-get-limited': {'tool':'curl', 'label':'HTTP GET limited body', 'hint':'One exact URL; no redirects; bounded body size and timeout.'},
    'web-fingerprint': {'tool':'whatweb', 'label':'Conservative web fingerprint', 'hint':'One exact URL, passive aggression level 1; no plugins or target expansion.'},
}


def scope_stamp(eng: dict) -> str:
    return hashlib.sha256(json.dumps([eng['include'], eng.get('exclude', []), eng.get('notes', ''), eng.get('program_url', '')], sort_keys=True).encode()).hexdigest()


def recipe(profile: str, target: str) -> list[str]:
    t = normalize_target(target)
    if profile in ('http-headers','http-options','http-status','http-get-limited','web-fingerprint'):
        if '://' not in t:
            raise ValueError('HTTP recipes need a full http:// or https:// URL')
        if profile == 'web-fingerprint':
            return ['--color=never','--aggression=1','--max-threads=1',t]
        args=['-q', '--silent', '--show-error', '--connect-timeout', '5', '--max-time', '20', '--proto', '=http,https']
        if profile in ('http-headers','http-options'): args.append('--head')
        if profile=='http-options': args.extend(['--request','OPTIONS'])
        if profile=='http-status': args.extend(['--output','/dev/null','--write-out','HTTP %{http_code}\nTLS %{ssl_verify_result}\nTime %{time_total}s\n'])
        if profile=='http-get-limited': args.extend(['--max-filesize','262144'])
        return [*args, '--url', t]
    if '://' in t:
        raise ValueError('This recipe needs a hostname or IP, not a URL')
    if profile == 'tcp-connect':
        return ['-sT', '-Pn', '-n', '-sV', '--version-light', '--top-ports', '100', '--max-rate', '10', '--max-retries', '1', '--host-timeout', '60s', t]
    if profile == 'tcp-web':
        return ['-sT', '-Pn', '-n', '-sV', '--version-light', '-p', '80,443,8080,8443', '--max-rate', '10', '--max-retries', '1', '--host-timeout', '60s', t]
    if profile == 'tls-certificate':
        # No URL-only grant may be used for host-wide TLS probing.
        # Host is validated as a single hostname / IP by normalize_target.
        tls_host = f'[{t}]' if ':' in t else t
        return ['s_client','-brief','-showcerts','-connect',f'{tls_host}:443','-servername',t]
    if profile in ('dns-a','dns-aaaa','dns-mx','dns-txt','dns-caa','dns-ns','dns-soa','dns-cname'):
        return ['-r', '+time=3', '+tries=1', t, {'dns-a':'A','dns-aaaa':'AAAA','dns-mx':'MX','dns-txt':'TXT','dns-caa':'CAA','dns-ns':'NS','dns-soa':'SOA','dns-cname':'CNAME'}[profile]]
    if profile == 'whois':
        return ['--', t]
    raise ValueError('Unknown guided recipe')


class JobManager:
    def __init__(self, cfg: Settings, store: Store, registry: Registry):
        self.cfg, self.store, self.registry = cfg, store, registry
        self.hardware = None
        self.tasks: dict[str, asyncio.Task] = {}
        self.processes: dict[str, asyncio.subprocess.Process] = {}
        self.reasons: dict[str, str] = {}
        self.lock = asyncio.Lock()
        self.directory = cfg.state / 'jobs'
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    def recover(self):
        for owner, job in self.store.all('job'):
            if job['status'] in ACTIVE:
                job.update(status='interrupted', ended=now(), error='Service restarted; this job was not automatically repeated.')
                self.store.put('job', owner, job)

    def engagement(self, owner: str, id: str) -> dict:
        eng = self.store.get('engagement', id, owner)
        if not eng:
            raise HTTPException(404, 'Engagement not found')
        return eng

    def prepare(self, owner: str, spec: ProposalSpec, source: str = 'operator') -> dict:
        eng = self.engagement(owner, spec.engagement_id)
        guided = spec.profile != 'advanced'
        args = spec.args
        if guided:
            if PROFILES[spec.profile]['tool'] != spec.tool:
                raise HTTPException(400, 'Recipe and tool do not match')
            if not allowed(spec.target, eng['include'], eng.get('exclude', [])):
                raise HTTPException(403, 'Target is outside the saved engagement input scope. Review exact assets and exclusions.')
            try:
                args = recipe(spec.profile, spec.target)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        try:
            item = self.registry.resolve(spec.tool)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if item['mode'] in ('interactive', 'gui'):
            raise HTTPException(400, 'This tool needs an interactive terminal or desktop. Open it there; this job runner has no interactive stdin.')
        selected_interface = None
        if spec.interface_name:
            # Only curl's fixed guided recipes currently support binding. The
            # configured name must be an explicitly assigned assessment NIC,
            # and is revalidated at approval time. Never silently select a NIC.
            if spec.profile not in ('http-headers','http-options','http-status','http-get-limited') or spec.tool!='curl':
                raise HTTPException(422,'Interface binding currently supports guided Curl HTTP recipes only')
            if self.hardware is None:
                raise HTTPException(503,'Hardware inventory unavailable')
            selected_interface = self.hardware.require_assessment(owner,spec.interface_name)
            args = ['--interface','if!'+spec.interface_name,*args]
        argv = [item['path'], *args]
        pending = [p for p in self.store.list('proposal', owner, 100) if p['status'] == 'pending' and p['expires'] > time.time()]
        if len(pending) >= 30:
            raise HTTPException(429, 'Too many pending proposals. Review or dismiss earlier proposals first.')
        data = {'id':identifier(), 'engagement_id':eng['id'], 'tool':spec.tool, 'argv':argv,
                'command':shlex.join(argv), 'profile':spec.profile, 'target':spec.target,
                'reason':spec.reason or 'Operator-requested tool run', 'source':source,
                'scope_check':'input-checked' if guided else 'manual-review',
                'scope_stamp':scope_stamp(eng), 'fingerprint':self.registry.fingerprint(item['path']),
                'warnings':[item['note'], 'Input checks are not network containment. Full shell and advanced tools can reach outside scope.',
                            'No interactive stdin. Use the terminal for prompts, pipelines, shell expansion or GUI tools.'],
                'interface_name':spec.interface_name, 'interface_identity':selected_interface['identity'] if selected_interface else '',
                'expires':time.time() + 600, 'status':'pending', 'timeout':self.cfg.job_timeout}
        data['digest'] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        self.store.event(owner, 'proposal-created', data['id'])
        return self.store.put('proposal', owner, data)

    def prepare_registered(self, owner: str, engagement_id: str, adapter: dict,
                           target: str, parameters: dict, reason: str,
                           revision: str, source: str = 'adapter-preview') -> dict:
        """Root-policy templated command; no model-provided executable, flags or argv."""
        from .adapters import AdapterPolicy
        from .command_templates import compile_template
        policy=AdapterPolicy(self.cfg.adapter_policy_path).current()
        if policy['status']!='active' or policy['revision']!=revision:
            raise HTTPException(409,'Administrator tool policy changed. Refresh before proceeding.')
        aid=adapter['id']
        if aid not in policy['enabled_profiles'] or policy.get('registered_adapters',{}).get(aid)!=adapter:
            raise HTTPException(403,'Tool adapter is not currently authorized')
        if source=='rabbit-hole' and adapter['mode']!='autonomous':
            raise HTTPException(403,'This tool requires per-command operator review')
        eng=self.engagement(owner,engagement_id)
        if not allowed(target,eng['include'],eng.get('exclude',[])):
            raise HTTPException(403,'The adapter target is outside the engagement scope')
        try:
            argv=compile_template(adapter,target,parameters)
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc
        p=self.prepare(owner,ProposalSpec(engagement_id=engagement_id,tool=adapter['tool'],
            args=argv,profile='advanced',target=target,reason=reason),source=source)
        p.update(profile=aid,scope_check='admin-template-input-checked',
                 adapter_policy_revision=revision,adapter_id=aid,
                 warnings=[*p['warnings'],'Administrator template, not network sandbox. Verify tool version, redirects, traffic behavior and permitted methods.'])
        p['digest']=hashlib.sha256(json.dumps({k:v for k,v in p.items() if k!='digest'},sort_keys=True).encode()).hexdigest()
        return self.store.put('proposal',owner,p)

    async def approve(self, owner: str, id: str, digest: str, authorized: bool) -> dict:
        async with self.lock:
            p = self.store.get('proposal', id, owner)
            if not p:
                raise HTTPException(404, 'Proposal not found')
            if not authorized:
                raise HTTPException(400, 'Confirm scope, methods and exact command before running')
            if p['status'] != 'pending':
                raise HTTPException(409, 'This proposal was already used or dismissed; it cannot run twice')
            if p['expires'] < time.time():
                raise HTTPException(409, 'Proposal expired. Prepare a fresh proposal to recheck the command.')
            if not hmac.compare_digest(digest, p['digest']):
                raise HTTPException(409, 'Proposal changed. Reopen the preview before approving.')
            if p.get('run_id'):
                self._check_delegation(owner,p)
            if p.get('adapter_id'):
                from .adapters import AdapterPolicy
                current=AdapterPolicy(self.cfg.adapter_policy_path).current()
                if current['status']!='active' or current['revision']!=p['adapter_policy_revision'] or p['adapter_id'] not in current['enabled_profiles']:
                    raise HTTPException(409,'Administrator adapter policy changed or was revoked')
            if p.get('interface_name'):
                if self.hardware is None:
                    raise HTTPException(409,'Hardware inventory unavailable')
                nic=self.hardware.require_assessment(owner,p['interface_name'])
                if nic['identity']!=p.get('interface_identity'):
                    raise HTTPException(409,'Assessment interface changed; prepare a new proposal')
            eng = self.engagement(owner, p['engagement_id'])
            if scope_stamp(eng) != p['scope_stamp']:
                raise HTTPException(409, 'Engagement scope changed. Prepare a fresh proposal.')
            try:
                item = self.registry.resolve(p['tool'])
                if self.registry.fingerprint(item['path']) != p['fingerprint']:
                    raise ValueError('Executable changed')
            except (ValueError, OSError) as exc:
                raise HTTPException(409, 'Tool changed or is missing. Refresh inventory and prepare a fresh proposal.') from exc
            if len(self.tasks) >= self.cfg.max_jobs:
                raise HTTPException(429, 'The node job limit is reached. Wait for a job to finish or stop one; this proposal remains pending.')
            if shutil.disk_usage(self.cfg.state).free < self.cfg.reserve_bytes:
                raise HTTPException(507, 'Low disk space: export/archive evidence and free disk space before starting another job.')
            p['status'] = 'approved'
            self.store.put('proposal', owner, p)
            id = identifier()
            job = {'id':id, 'engagement_id':p['engagement_id'], 'proposal_id':p['id'], 'tool':p['tool'],
                   'argv':p['argv'], 'command':p['command'], 'scope_check':p['scope_check'],
                   'interface_name':p.get('interface_name',''),
                   'status':'queued', 'returncode':None, 'started':None, 'ended':None,
                   'output_bytes':0, 'error':'', 'timeout':self.cfg.job_timeout}
            if p.get('run_id'):
                job.update(run_id=p['run_id'],run_instruction_revision=p['run_instruction_revision'])
            self.store.put('job', owner, job)
            self.store.event(owner, 'job-approved', id)
            self.tasks[id] = asyncio.create_task(self._worker(owner, job))
            return job

    def delegate(self,owner: str,proposal: dict,run_id: str,instruction_revision: int) -> dict:
        """Bind a prepared proposal to an existing explicit run authorization."""
        proposal.update(run_id=run_id,run_instruction_revision=instruction_revision)
        self._check_delegation(owner,proposal)
        if proposal['profile']=='advanced':proposal['scope_check']='operator-run-grant'
        proposal['digest']=hashlib.sha256(json.dumps({k:v for k,v in proposal.items() if k!='digest'},sort_keys=True).encode()).hexdigest()
        return self.store.put('proposal',owner,proposal)

    def _check_delegation(self,owner: str,proposal: dict):
        from .adapters import AdapterPolicy
        grant=self.store.get('rabbit',proposal['run_id'],owner)
        if not grant or grant['status'] not in ('queued','running'):
            raise HTTPException(409,'Rabbit Hole run authorization is no longer active')
        policy=AdapterPolicy(self.cfg.adapter_policy_path).current()
        if policy['status']!='active' or policy['revision']!=grant['policy_revision']:
            raise HTTPException(409,'Administrator run policy changed or was revoked')
        if grant.get('instruction_revision',0)!=proposal['run_instruction_revision']:
            raise HTTPException(409,'Operator instructions changed; replan the command')
        if time.time()>=grant['budget_end'] or grant.get('decisions_used',0)>grant['max_steps']:
            raise HTTPException(409,'Run authorization budget expired')
        if grant['max_steps']>policy['max_steps'] or grant['max_minutes']>policy['max_minutes']:
            raise HTTPException(409,'Run budget exceeds administrator policy')
        eng=self.engagement(owner,grant['engagement_id'])
        if (proposal['engagement_id']!=grant['engagement_id']
                or (proposal['profile']=='advanced' and proposal['target']!=grant['target'])
                or scope_stamp(eng)!=grant['authorization_stamp']):
            raise HTTPException(409,'Engagement authorization changed')
        if not allowed(grant['target'],eng['include'],eng.get('exclude',[])):
            raise HTTPException(403,'Run target is outside the saved engagement scope')
        if grant.get('execution_mode','workflows')=='installed_cli':
            if not policy.get('allow_installed_cli',False):raise HTTPException(403,'Installed CLI autonomy is disabled')
        elif proposal['profile'] not in grant['profiles']:
            raise HTTPException(403,'Tool is outside the run workflow authorization')

    async def _terminate(self, proc):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), 2)
        except asyncio.TimeoutError:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
        finally:
            # The group may still contain children after its leader has exited.
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass

    async def _worker(self, owner: str, job: dict):
        id, proc = job['id'], None
        base = self.directory / id
        base.mkdir(mode=0o700)
        total = 0
        try:
            if id in self.reasons:
                job['status'] = self.reasons[id]
                return
            # Approval and actual process creation are separate scheduling points.
            if job.get('run_id'):
                proposal=self.store.get('proposal',job['proposal_id'],owner)
                if not proposal:raise HTTPException(409,'Delegated proposal disappeared')
                self._check_delegation(owner,proposal)
                item=self.registry.resolve(proposal['tool'])
                if self.registry.fingerprint(item['path'])!=proposal['fingerprint']:
                    raise HTTPException(409,'Executable changed before autonomous launch')
            proc = await asyncio.create_subprocess_exec(*job['argv'], cwd=self.store.workspace(job['engagement_id']),
                        env=child_environment(self.cfg), stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True)
            self.processes[id] = proc
            job.update(status='running', started=now(), pid=proc.pid)
            self.store.put('job', owner, job)
            if id in self.reasons:
                await self._terminate(proc)
            with (base/'combined.log').open('wb') as combined, (base/'stdout.log').open('wb') as stdout, (base/'stderr.log').open('wb') as stderr:
                async def drain(stream, output):
                    nonlocal total
                    while True:
                        data = await stream.read(16384)
                        if not data:
                            return
                        piece = data[:max(0, self.cfg.log_bytes - total)]
                        if piece:
                            combined.write(piece); combined.flush()
                            output.write(piece); output.flush()
                            total += len(piece)
                        if len(piece) < len(data):
                            self.reasons[id] = 'output_limit'
                            await self._terminate(proc)
                            return
                readers = [asyncio.create_task(drain(proc.stdout, stdout)), asyncio.create_task(drain(proc.stderr, stderr))]
                try:
                    await asyncio.wait_for(proc.wait(), self.cfg.job_timeout)
                except asyncio.TimeoutError:
                    self.reasons[id] = 'timed_out'
                    await self._terminate(proc)
                try:
                    await asyncio.wait_for(asyncio.gather(*readers), 3)
                except asyncio.TimeoutError:
                    self.reasons.setdefault(id, 'failed')
                    job['error'] = 'A descendant process kept output open; use a supervised foreground command.'
                    try: os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                job['returncode'] = proc.returncode
                job['status'] = self.reasons.get(id, 'succeeded' if proc.returncode == 0 else 'failed')
        except asyncio.CancelledError:
            job['status'] = 'interrupted'
            if proc: await self._terminate(proc)
        except Exception as exc:
            job.update(status='failed', error=f'Launch/read error: {type(exc).__name__}. Check executable, dependencies and permissions.')
        finally:
            if proc and proc.returncode is None:
                await self._terminate(proc)
            job.update(ended=now(), output_bytes=total)
            self.store.put('job', owner, job)
            self.store.event(owner, 'job-' + job['status'], id)
            self.tasks.pop(id, None); self.processes.pop(id, None); self.reasons.pop(id, None)

    async def stop(self, owner: str, id: str) -> dict:
        job = self.store.get('job', id, owner)
        if not job:
            raise HTTPException(404, 'Job not found')
        if id not in self.tasks:
            return {'stop_requested':False, 'status':job['status']}
        self.reasons[id] = 'stopped'
        job['status'] = 'stopping'
        self.store.put('job', owner, job)
        proc = self.processes.get(id)
        if proc:
            await self._terminate(proc)
        self.store.event(owner, 'job-stop-requested', id)
        return {'stop_requested':True, 'status':'stopping'}

    async def delete(self, owner: str, id: str) -> dict:
        """Delete an owned finished job and its captured logs, never workspace files."""
        if len(id)!=24 or any(c not in '0123456789abcdef' for c in id):
            raise HTTPException(404,'Job not found')
        async with self.lock:
            job=self.store.get('job',id,owner)
            if not job:raise HTTPException(404,'Job not found')
            if job.get('status') not in FINISHED or id in self.tasks or id in self.processes:
                raise HTTPException(409,'Stop the job and wait for it to finish before deleting it.')
            with self.store.db() as db:
                rows=db.execute("SELECT id,data FROM records WHERE kind='rabbit' AND owner=? AND json_extract(data,'$.engagement_id')=?",
                                (owner,job['engagement_id'])).fetchall()
                linked=[]
                for row in rows:
                    run=json.loads(row['data'])
                    if any(step.get('job_id')==id for step in run.get('steps',[])):
                        if run.get('status') in ACTIVE:
                            raise HTTPException(409,'Stop or finish the Rabbit Hole run before deleting one of its jobs.')
                        linked.append(run)
                # Anchor removal to the opened jobs directory. Neither a job
                # directory symlink nor nested symlinks may redirect deletion.
                root_fd=None
                try:
                    root_fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                    try:mode=os.stat(id,dir_fd=root_fd,follow_symlinks=False).st_mode
                    except FileNotFoundError:mode=None
                    if mode is not None:
                        if stat.S_ISLNK(mode):os.unlink(id,dir_fd=root_fd)
                        elif stat.S_ISDIR(mode):shutil.rmtree(id,dir_fd=root_fd)
                        else:raise HTTPException(409,'The job log path is not a directory; the job was kept.')
                except FileNotFoundError:
                    pass  # Missing logs do not prevent removing a finished record.
                except OSError as exc:
                    raise HTTPException(500,'Could not remove the captured logs. The job record was kept; retry after checking storage permissions.') from exc
                finally:
                    if root_fd is not None:os.close(root_fd)
                db.execute("DELETE FROM records WHERE kind='job' AND id=? AND owner=?",(id,owner))
                db.execute("DELETE FROM records WHERE kind='graph_note' AND owner=? AND json_extract(data,'$.node_id')=?",(owner,'job:'+id))
                for run in linked:
                    for step in run.get('steps',[]):
                        if step.get('job_id')==id:step['job_deleted']=True
                    db.execute("UPDATE records SET data=? WHERE kind='rabbit' AND id=? AND owner=?",
                               (json.dumps(run,ensure_ascii=False),run['id'],owner))
            # Keep the consumed proposal and audit history; deletion must never
            # make a previously approved proposal executable a second time.
            self.store.event(owner,'job-deleted',id)
            return {'deleted':True,'id':id}

    def output(self, id: str, owner: str, offset: int = 0) -> dict:
        job = self.store.get('job', id, owner)
        if not job:
            raise HTTPException(404, 'Job not found')
        path = self.directory / id / 'combined.log'
        text, new_offset = '', offset
        if path.exists():
            with path.open('rb') as f:
                f.seek(min(max(0, offset), path.stat().st_size))
                data = f.read(65536)
                decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
                complete = f.tell() >= path.stat().st_size and job['status'] not in ACTIVE
                text = decoder.decode(data, final=complete)
                new_offset = f.tell() - len(decoder.getstate()[0])
        return {'text':text, 'offset':new_offset, 'job':job}

    async def shutdown(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
