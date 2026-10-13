"""Evidence-linked read-only graph projection for managed jobs and Rabbit Hole runs.

Canonical job and run records are persistent, so graphs survive restarts.
Annotations are separately persisted and per-owner. No model-derived node is a
verified security finding. The full shell is intentionally not reconstructed.
"""
from __future__ import annotations
from hashlib import sha256
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import HTTPException
from .graph_extractors import parse_observations
from .store import Store, now

MAX_JOBS=160
MAX_RUNS=70
MAX_OBSERVATIONS_PER_JOB=5

@lru_cache(maxsize=256)
def _cached_observations(path: str, byte_count: int, mtime_ns: int, tool: str) -> tuple[tuple, ...]:
    """Cache successful immutable job output parses; invalidate on file metadata change."""
    with open(path,'rb') as f:
        sample=f.read(131072).decode('utf-8','replace')
    return tuple(tuple(entry.items()) for entry in parse_observations(tool,sample,max_items=MAX_OBSERVATIONS_PER_JOB))

class InvestigationGraph:
    def __init__(self, store: Store, state: Path):
        self.store=store
        self.jobs_dir=state/'jobs'

    def _engagement(self, owner: str, engagement_id: str) -> dict:
        eng=self.store.get('engagement',engagement_id,owner)
        if not eng: raise HTTPException(404,'Engagement not found')
        return eng

    def get(self,owner: str,engagement_id: str) -> dict:
        engagement=self._engagement(owner,engagement_id)
        root='engagement:'+engagement_id
        nodes=[{'id':root,'kind':'engagement','label':engagement.get('name','Engagement')[:90],
                'status':'active','created':engagement.get('created',''),'origin':'operator',
                'description':'Authorized engagement; scope and exclusions are managed outside this graph.'}]
        edges=[];edge_keys=set()
        def link(source,target,kind,label=''):
            key=(source,target,kind)
            if key not in edge_keys:
                edge_keys.add(key);edges.append({'source':source,'target':target,'kind':kind,'label':label})
        runs=self.store.list('rabbit',owner,limit=MAX_RUNS,engagement_id=engagement_id)
        jobs=self.store.list('job',owner,limit=MAX_JOBS,engagement_id=engagement_id)
        jobs_by_id={x['id']:x for x in jobs}
        rabbit_jobs=set()
        assets={}  # Authorized guided-proposal targets only; never infer from raw output.
        # Oldest to newest provides a stable graph even when jobs update while viewed.
        for run in reversed(runs):
            rid='run:'+run['id'];steps=run.get('steps',[])
            nodes.append({'id':rid,'kind':'run','label':str(run.get('objective') or 'Rabbit Hole investigation')[:90],
                'status':run.get('status','unknown'),'created':run.get('created',''),
                'origin':'rabbit-hole','run_id':run['id'],'model':run.get('model',''),
                'description':str(run.get('summary') or 'AI investigation; reported conclusions are unverified.')[:350],
                'step_count':len(steps)})
            link(root,rid,'investigation')
            previous=None;previous_status=None
            for step in steps[:160]:
                jid=step.get('job_id')
                # Disconnected/missing history still gets a visible decision node.
                sid=('job:'+jid) if jid in jobs_by_id else ('step:'+run['id']+':'+str(step.get('number',0)))
                if jid in jobs_by_id:
                    rabbit_jobs.add(jid)
                else:
                    nodes.append({'id':sid,'kind':'step','label':str(step.get('profile','Step'))[:80],
                        'status':step.get('status','unknown'),'origin':'rabbit-hole','created':run.get('created',''),
                        'run_id':run['id'],'description':str(step.get('detail') or step.get('reason') or '')[:250]})
                link(rid,sid,'run-step')
                if previous and previous!=sid:
                    link(previous,sid,'retry' if previous_status in ('failed','blocked','timed_out','output_limit','stopped') else 'next',
                         'Alternate approach' if previous_status in ('failed','blocked','timed_out','output_limit','stopped') else 'Next step')
                previous=sid;previous_status=step.get('status')
        for job in reversed(jobs):
            aid=None
            jid='job:'+job['id'];origin='rabbit-hole' if job['id'] in rabbit_jobs else 'manual'
            status=job.get('status','unknown')
            nodes.append({'id':jid,'kind':'job','label':str(job.get('tool') or 'Managed tool')[:70],
                          'status':status,'origin':origin,'created':job.get('started') or job.get('created',''),
                          'ended':job.get('ended'),'returncode':job.get('returncode'),
                          'tool':job.get('tool',''),'job_id':job['id'],
                          'description':'Managed execution; open Jobs for recorded command and complete output.',
                          'evidence':'Saved job output' if status not in ('queued',) else 'Output pending'})
            if origin=='manual':link(root,jid,'manual-job')
            proposal=self.store.get('proposal',job.get('proposal_id',''),owner) if job.get('proposal_id') else None
            if (proposal and proposal.get('engagement_id')==engagement_id
                    and proposal.get('scope_check') in ('input-checked','admin-template-input-checked')
                    and isinstance(proposal.get('target'),str) and proposal['target']):
                target=proposal['target'][:180]
                # Record a reported target relation, not proof that a host was reached.
                asset_label=(urlsplit(target).hostname or target) if '://' in target else target
                if asset_label and len(asset_label)<=180:
                    aid='asset:'+sha256(asset_label.lower().encode()).hexdigest()[:20]
                    if aid not in assets:
                        asset={'id':aid,'kind':'asset','label':asset_label[:85],
                            'status':'scoped','origin':'approved-target','created':job.get('created',''),
                            'description':'Target from operator-approved guided job; not proof of reachability.'}
                        assets[aid]=asset;nodes.append(asset);link(root,aid,'approved-target')
                    link(aid,jid,'target-of')
            # Do not parse partial/failed/error output into observation nodes.
            if status!='succeeded' or job.get('returncode',0) not in (0,None):continue
            p=self.jobs_dir/job['id']/'combined.log'
            if not p.is_file() or p.is_symlink():continue
            try:
                metadata=p.stat()
                observations=[dict(items) for items in _cached_observations(str(p),metadata.st_size,metadata.st_mtime_ns,job.get('tool',''))]
            except OSError: continue
            for obj in observations:
                digest=sha256((job['id']+'\0'+obj['kind']+'\0'+obj['value']).encode()).hexdigest()[:20]
                oid='observation:'+digest
                nodes.append({'id':oid,'kind':'observation','label':obj['label'],'status':'observed',
                              'created':job.get('ended') or job.get('created',''),
                              'origin':'tool-parser','evidence_job_id':job['id'],
                              'observation_kind':obj['kind'],'confidence':'parsed-unverified',
                              'description':obj['provenance']})
                link(jid,oid,'tool-observation')
                if proposal and proposal.get('scope_check') in ('input-checked','admin-template-input-checked') and aid in assets:
                    link(aid,oid,'observed-for')
        notes={n['node_id']:n.get('note','') for n in self.store.list('graph_note',owner,limit=500,engagement_id=engagement_id)}
        for node in nodes:
            if node['id'] in notes:node['note']=notes[node['id']]
        counts={}
        for node in nodes:
            if node['kind']=='job':counts[node['status']]=counts.get(node['status'],0)+1
        return {'engagement_id':engagement_id,'generated_at':now(),'nodes':nodes,'edges':edges,
                'counts':counts,'truncated':len(jobs)>=MAX_JOBS or len(runs)>=MAX_RUNS,
                'notice':'Evidence-backed execution graph. Parsed observations are unverified. Terminal commands are not individually recorded.'}

    def annotate(self,owner: str,engagement_id: str,node_id: str,note: str) -> dict:
        if not isinstance(note,str) or len(note)>1200:
            raise HTTPException(422,'Annotations must contain at most 1200 characters')
        graph=self.get(owner,engagement_id)
        if not any(n['id']==node_id for n in graph['nodes']):
            raise HTTPException(404,'Graph node not found in this engagement')
        key=sha256((engagement_id+'\0'+node_id).encode()).hexdigest()[:24]
        if not note.strip():
            self.store.delete('graph_note',key,owner)
            self.store.event(owner,'graph-annotation-cleared',node_id[:150])
            return {'node_id':node_id,'note':''}
        saved=self.store.put('graph_note',owner,{'id':key,'engagement_id':engagement_id,'node_id':node_id,'note':note.strip()})
        self.store.event(owner,'graph-annotation-saved',node_id[:150])
        return saved
