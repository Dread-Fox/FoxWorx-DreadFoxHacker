"""Local ranked discovery. Inventory size does not determine model context size."""
from __future__ import annotations
import base64
import hashlib
import json
import re
import secrets
import sqlite3
import subprocess
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path

STOP_WORDS=set('a an and are as at be by can could do for from how i in is it me of on or please that the this to tool tools use using want what which with would'.split())
ALIASES={'website':('web','http'),'websites':('web','http'),'domain':('dns',),
         'certificates':('certificate','tls'),'ports':('port','network')}
LOOKUP_PARAMETERS={'type':'object','properties':{
    'query':{'type':'string','description':'Task description or executable name.'},
    'category':{'type':'string','description':'Exact category, or empty for all.'},
    'mode':{'type':'string','enum':['','cli','interactive','gui','unknown']},
    'cursor':{'type':'string','description':'next_cursor from the same search, or empty.'},
    'limit':{'type':'integer','minimum':1,'maximum':40}},
    'required':['query'],'additionalProperties':False}


def tokens(value):
    return set(re.findall(r'[a-z0-9]+',str(value).casefold()))-STOP_WORDS


def clean(value,limit):
    return ''.join(c for c in str(value) if c.isprintable() or c==' ').strip()[:limit]


def _read_command(argv):
    """Only fixed system metadata utilities; bound memory and utility runtime."""
    with tempfile.TemporaryFile() as output:
        subprocess.run(argv,stdout=output,stderr=subprocess.DEVNULL,timeout=5,check=False,
                       env={'PATH':'/usr/bin:/bin','LC_ALL':'C.UTF-8'})
        output.seek(0)
        return output.read(4*1024*1024).decode('utf-8','replace')


class LocalMetadata:
    """Persistent public metadata only: never index private operator notes."""
    def __init__(self,state):
        self.path=Path(state)/'tool-discovery.sqlite3'

    def __call__(self,rows,stop):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS summaries (name TEXT PRIMARY KEY, identity TEXT, value TEXT)')
            self.path.chmod(0o600)
            cached={n:(identity,json.loads(value)) for n,identity,value in db.execute('SELECT name,identity,value FROM summaries')}
            summaries={}; missing=[];identities={}
            try:
                status=Path('/var/lib/dpkg/status').stat()
                package_stamp=(status.st_mtime_ns,status.st_size)
            except OSError:package_stamp=()
            for row in rows:
                if stop.is_set():return summaries
                try:
                    p=Path(row['path']);s=p.stat()
                    identity=str((str(p.resolve()),s.st_ino,s.st_size,s.st_mtime_ns,row.get('version',''),package_stamp))
                except OSError:continue
                name=row['name'];identities[name]=identity
                if name in cached and cached[name][0]==identity:summaries[name]=cached[name][1]
                else:missing.append(row)
            packages={};owners={}
            if missing and not stop.is_set():
                try:
                    for line in _read_command(['/usr/bin/dpkg-query','-W','-f=${binary:Package}\t${Version}\t${binary:Summary}\n']).splitlines():
                        parts=line.split('\t',2)
                        if len(parts)==3:packages[parts[0].split(':')[0]]=(parts[1],parts[2])
                    wanted={row['path']:row['name'] for row in missing}
                    wanted.update({str(Path(row['path']).resolve()):row['name'] for row in missing})
                    for listing in Path('/var/lib/dpkg/info').glob('*.list'):
                        if stop.is_set():return summaries
                        try:
                            with listing.open(errors='replace') as stream:
                                for line in stream:
                                    name=wanted.get(line.rstrip('\n'))
                                    if name:owners[name]=listing.name[:-5].split(':')[0]
                        except OSError:continue
                except (OSError,subprocess.TimeoutExpired):pass
            for start in range(0,len(missing),128):
                if stop.is_set():break
                batch=missing[start:start+128];manuals={}
                try:
                    output=_read_command(['/usr/bin/whatis','--',*[row['name'] for row in batch]])
                    for line in output.splitlines():
                        match=re.match(r'^(.+?)\s+\([18][^)]*\)\s+-\s+(.+)$',line)
                        if match:
                            for name in match[1].split(','):
                                manuals.setdefault(name.strip(),match[2])
                except (OSError,subprocess.TimeoutExpired):pass
                for row in batch:
                    name=row['name'];package=row.get('package') or owners.get(name,'')
                    version,description=packages.get(package,('',''))
                    summary=manuals.get(name) or description
                    value={'summary':clean(summary,400),'source':'man' if name in manuals else 'package' if description else '',
                           'package':package,'version':version}
                    summaries[name]=value
                    db.execute('REPLACE INTO summaries VALUES (?,?,?)',(name,identities[name],json.dumps(value)))
                db.commit()
            present={row['name'] for row in rows}
            db.executemany('DELETE FROM summaries WHERE name=?',[(name,) for name in cached if name not in present])
            return summaries


class ToolDiscovery:
    def __init__(self,registry,state,metadata_reader=None):
        self.registry=registry
        self.metadata_reader=metadata_reader or LocalMetadata(state)
        self._snapshot=None;self._metadata={};self._generation=0
        self._instance=secrets.token_hex(8)
        self._lock=threading.RLock();self._stop=threading.Event();self._thread=None
        self._last_attempt=0.;self._refresh_error=False

    def rebuild(self,metadata=None):
        with self._lock:
            if metadata is None and self._snapshot and self._snapshot['scanned_at']!=self.registry.scanned:
                self._metadata={}
            if metadata is not None:self._metadata=metadata
            rows=[dict(r) for r in self.registry.list() if r.get('installed')]
            postings=defaultdict(dict);entries={};categories=defaultdict(int)
            for row in rows:
                name=row['name'];meta=self._metadata.get(name,{})
                description=clean(row.get('description',''),240)
                summary=clean(meta.get('summary',''),300)
                category=clean(row.get('category','System / additional'),80)
                mode=row.get('mode','unknown')
                entries[name]={'name':name,'description':description,'summary':summary,'category':category,
                    'mode':mode,'version':clean(row.get('version') or meta.get('version',''),80),
                    'installed':True,'metadata_sources':[meta['source']] if meta.get('source') else [],
                    'note':clean(row.get('note',''),180)}
                categories[category]+=1
                fields=((name,8),(category,4),(description+' '+summary,3),(row.get('package','') or meta.get('package',''),1))
                for value,weight in fields:
                    for term in tokens(value):postings[term][name]=postings[term].get(name,0)+weight
            self._generation+=1
            self._snapshot={'entries':entries,'names':sorted(entries,key=str.casefold),'postings':dict(postings),
                'categories':dict(sorted(categories.items(),key=lambda p:(-p[1],p[0]))[:20]),
                'revision':f'{self._instance}:{self._generation}','scanned_at':self.registry.scanned}
            return self._snapshot

    def request_refresh(self,enrich_only=False):
        with self._lock:
            if self._stop.is_set() or (self._thread and self._thread.is_alive()):return
            if not enrich_only and time.monotonic()-self._last_attempt<60:return
            self._last_attempt=time.monotonic()
            def refresh():
                try:
                    if not enrich_only:self.registry.scan()
                    self.rebuild()
                    scanned_at=self.registry.scanned
                    metadata=self.metadata_reader(self.registry.list(),self._stop)
                    if not self._stop.is_set() and self.registry.scanned==scanned_at:self.rebuild(metadata)
                    self._refresh_error=False
                except Exception:self._refresh_error=True
            self._thread=threading.Thread(target=refresh,name='foxworx-discovery',daemon=True)
            self._thread.start()

    def search(self,query='',category='',mode='',cursor='',limit=20):
        if not isinstance(query,str) or len(query)>4000:raise ValueError('Query must be at most 4000 characters')
        if not isinstance(category,str) or len(category)>80:raise ValueError('Invalid category')
        if mode not in ('','cli','interactive','gui','unknown'):raise ValueError('Invalid execution mode')
        if type(limit) is not int or not 1<=limit<=40:raise ValueError('Page size must be from 1 to 40')
        if not isinstance(cursor,str) or len(cursor)>500:raise ValueError('Invalid search cursor')
        if self._snapshot is None:self.rebuild()
        snap=self._snapshot
        stale=time.time()-self.registry.scanned>60
        if stale:self.request_refresh()
        result={'results':[],'total_matches':0,'returned':0,'next_cursor':None,
            'inventory_revision':snap['revision'],'installed_count':len(snap['entries']),
            'categories':snap['categories'],'scanned_at':snap['scanned_at'],'stale':stale,
            'refreshing':bool(self._thread and self._thread.is_alive()),'refresh_error':self._refresh_error,
            'restart_required':False}
        signature=hashlib.sha256(json.dumps([query,category,mode],ensure_ascii=True).encode()).hexdigest()[:16]
        offset=0
        if cursor:
            try:
                revision,old_signature,offset=json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
                if type(offset) is not int or offset<0:raise ValueError()
            except Exception:raise ValueError('Invalid search cursor') from None
            if revision!=snap['revision'] or old_signature!=signature:
                result.update(restart_required=True,message='Inventory or query changed; restart without a cursor.')
                return result
        terms=tokens(query)
        for term in tuple(terms):terms.update(ALIASES.get(term,()))
        scores=defaultdict(int);matches=defaultdict(set)
        for term in terms:
            for name,weight in snap['postings'].get(term,{}).items():
                scores[name]+=weight;matches[name].add(term)
        exact=query.strip().casefold()
        if exact:
            # A bounded prefix range supports executable names with punctuation.
            names=snap['names'];lower=[exact] if exact in snap['entries'] else []
            for name in lower:scores[name]+=100;matches[name].add('exact name')
        candidates=list(scores) if terms else (snap['names'] if not query.strip() else [])
        candidates=[name for name in candidates if (not category or snap['entries'][name]['category']==category)
                    and (not mode or snap['entries'][name]['mode']==mode)]
        if terms:candidates.sort(key=lambda name:(-scores[name],name.casefold()))
        result['total_matches']=len(candidates)
        for name in candidates[offset:offset+limit]:
            entry={**snap['entries'][name],'match_reasons':sorted(matches[name])[:8]}
            if len(json.dumps(result,ensure_ascii=True).encode())+len(json.dumps(entry,ensure_ascii=True).encode())>30000:break
            result['results'].append(entry)
        result['returned']=len(result['results'])
        next_offset=offset+result['returned']
        if next_offset<len(candidates):
            result['next_cursor']=base64.urlsafe_b64encode(json.dumps([snap['revision'],signature,next_offset]).encode()).decode()
        return result

    def shortlist(self,query):
        return self.search(query=query[:4000],limit=10)

    def close(self):
        self._stop.set()
        if self._thread:self._thread.join(timeout=6)
