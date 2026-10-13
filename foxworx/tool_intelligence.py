"""Persistent, host-specific Kali CLI knowledge. References are untrusted DATA.

No arbitrary executable is invoked during indexing. Only a fixed man utility can
run to render public manuals. Online lookups are explicit, opt-in and restricted
to HTTPS official documentation hosts; they never authorize tool execution.
"""
from __future__ import annotations
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from urllib.parse import quote, urlsplit, urlencode
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from .registry import NAME, Registry

MAX_DOC = 12000
MAX_WEB_BODY = 150000
CACHE_SECONDS = 7 * 86400
FLAGS = re.compile(r'(?<![A-Za-z0-9_])--[A-Za-z][A-Za-z0-9-]{0,45}\b')
DOC_HOSTS = frozenset({'www.kali.org','manpages.debian.org','www.gnu.org','github.com'})

class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, hdrs, newurl):
        raise ValueError('Documentation redirects are not followed; a direct approved URL is required')

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','svg'):self.skip+=1
        if tag in ('p','h1','h2','h3','li','pre','br'):self.out.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','svg') and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.out.append(data)

def allowed_document_url(url: str) -> bool:
    try:
        p=urlsplit(url)
        return (p.scheme=='https' and p.hostname in DOC_HOSTS and p.port in (None,443)
                and p.username is None and p.password is None and not p.fragment
                and len(url)<1400 and not any(c in url for c in '\r\n\t\\'))
    except ValueError:
        return False

def _search_brave(name:str,key:str) -> list[dict]:
    # Server-held credential never goes to the model, browser, logs or search query.
    url='https://api.search.brave.com/res/v1/web/search?'+urlencode({
        'q':f'{name} command line usage site:kali.org OR site:github.com OR site:manpages.debian.org',
        'count':8})
    req=Request(url,headers={'X-Subscription-Token':key,'Accept':'application/json',
                             'User-Agent':'FOXWORX-ToolDocs/2.9'})
    opener=build_opener(ProxyHandler({}),_RejectRedirect())
    with opener.open(req,timeout=7) as response:
        if response.status!=200:raise ValueError('Documentation search unavailable')
        body=response.read(MAX_WEB_BODY+1)
        if len(body)>MAX_WEB_BODY:raise ValueError('Search response exceeds safety limit')
        decoded=json.loads(body.decode('utf-8','replace'))
    return [{'url':v.get('url',''), 'title':v.get('title',''), 'description':v.get('description','')}
            for v in decoded.get('web',{}).get('results',[])[:12] if isinstance(v,dict)]

def clean(raw: str) -> str:
    # Treat the source as data, not instructions. Strip terminal control and
    # unusual nonprinting characters before display, caching, or model use.
    raw=re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))','',str(raw))
    return ''.join(c for c in raw if c in '\n\t' or ord(c)>=32)[:MAX_DOC]

def _web_fetch(url: str, key: str = '') -> str:
    if not allowed_document_url(url):raise ValueError('Unapproved documentation host')
    opener=build_opener(ProxyHandler({}),_RejectRedirect())
    req=Request(url,headers={'User-Agent':'FOXWORX-ToolDocs/2.9','Accept':'text/html,text/plain'})
    with opener.open(req,timeout=6) as result:
        if result.status!=200:raise ValueError('Official documentation not available')
        if result.headers.get('content-type','').split(';')[0].lower() not in ('text/html','text/plain'):
            raise ValueError('Documentation response was not text')
        data=result.read(MAX_WEB_BODY+1)
        if len(data)>MAX_WEB_BODY:raise ValueError('Documentation page exceeds safety limit')
        decoded=data.decode('utf-8','replace')
        if 'html' in result.headers.get('content-type','').lower():
            parser=_Text();parser.feed(decoded);decoded=' '.join(parser.out)
        return clean(re.sub(r'[ \t]{3,}','  ',decoded))

def _local_read(tool: dict) -> tuple[str,str]:
    name=tool['name']
    # Man is the only system program run by the documentation reader. It never
    # invokes the discovered executable. Explicit program and environment.
    binary='/usr/bin/man'
    if Path(binary).is_file():
        try:
            outcome=subprocess.run([binary,'-P','cat','--',name],capture_output=True,
                timeout=4,check=False,env={'PATH':'/usr/bin:/bin','MANPAGER':'cat','PAGER':'cat',
                    'GROFF_NO_SGR':'1','LC_ALL':'C.UTF-8'})
            if outcome.returncode==0 and outcome.stdout:
                return 'man', clean(outcome.stdout[:MAX_DOC*3].decode('utf-8','replace'))
        except (OSError, subprocess.TimeoutExpired):pass
    package=str(tool.get('package') or '')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9+.-]{0,95}',package):return '',''
    base=Path('/usr/share/doc')/package
    # Single level only, no symlinks; never follow user-specified paths.
    for candidate in ('README.Debian','README','README.md','README.txt','usage.txt'):
        path=base/candidate
        try:
            if not path.is_symlink() and path.is_file() and path.stat().st_size<=200000:
                return 'package',clean(path.read_text('utf-8','replace'))
        except OSError:continue
    return '',''

class ToolIntelligence:
    def __init__(self,cfg,registry: Registry,*,local_reader=None,web_fetch=None,search_fetch=None):
        self.cfg,self.registry=cfg,registry
        self.local_reader=local_reader or _local_read
        self.web_fetch=web_fetch or _web_fetch
        self.search_fetch=search_fetch or _search_brave
        cfg.state.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path=cfg.state/'tool-intelligence.sqlite3'
        with self._db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
              name TEXT NOT NULL, identity TEXT NOT NULL, source TEXT NOT NULL,
              excerpt TEXT NOT NULL, location TEXT NOT NULL, fetched REAL NOT NULL,
              PRIMARY KEY(name,identity,source));
            CREATE TABLE IF NOT EXISTS notes (
              name TEXT NOT NULL, identity TEXT NOT NULL, owner TEXT NOT NULL,
              note TEXT NOT NULL, created REAL NOT NULL,
              PRIMARY KEY(name,identity,owner,note));
            CREATE INDEX IF NOT EXISTS docs_by_name ON documents(name);
            ''')
        self.path.chmod(0o600)

    def _db(self):
        # Fresh connection per operation, safe with asyncio.to_thread API handlers.
        return sqlite3.connect(self.path,timeout=5)

    def _identity(self,tool:dict)->str:
        fp=self.registry.fingerprint(tool['path'])
        raw=json.dumps({'path':tool['path'],'fingerprint':fp,'version':tool.get('version','')},sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def search(self,query='',limit=60)->list[dict]:
        term=query.strip().casefold()[:120]
        result=[]
        for tool in self.registry.list():
            if not tool['installed']:continue
            if term and term not in f"{tool['name']} {tool['description']} {tool.get('category','')}".casefold():continue
            result.append({'name':tool['name'],'description':tool['description'],
                           'category':tool['category'],'mode':tool.get('mode','unknown'),
                           'installed':True,'version':tool.get('version','')})
            if len(result)>=min(max(int(limit),1),100):break
        return result

    def _row(self,name,identity,source):
        with self._db() as db:
            return db.execute('SELECT excerpt,location,fetched FROM documents WHERE name=? AND identity=? AND source=?',
                              (name,identity,source)).fetchone()

    def _put_doc(self,name,identity,source,text,location):
        with self._db() as db:
            db.execute('REPLACE INTO documents VALUES (?,?,?,?,?,?)',
                (name,identity,source,clean(text),location,time.time()))
            # Bounded history; retain latest three executable revisions.
            revs=db.execute('SELECT identity,max(fetched) FROM documents WHERE name=? GROUP BY identity ORDER BY max(fetched) DESC',(name,)).fetchall()
            for old,_ in revs[3:]:
                db.execute('DELETE FROM documents WHERE name=? AND identity=?',(name,old))
                db.execute('DELETE FROM notes WHERE name=? AND identity=?',(name,old))

    def get(self,name:str,*,refresh=False,owner:str|None=None)->dict:
        if not isinstance(name,str) or not NAME.fullmatch(name):
            raise ValueError('Select one discovered tool name')
        tool=self.registry.resolve(name)
        identity=self._identity(tool)
        local=self._row(name,identity,'local')
        cached=bool(local and not refresh)
        if not cached:
            origin,doc=self.local_reader(tool)
            self._put_doc(name,identity,'local',doc,origin or 'not-found')
        docs=[]
        with self._db() as db:
            rows=db.execute('SELECT source,excerpt,location,fetched FROM documents WHERE name=? AND identity=? ORDER BY source',
                (name,identity)).fetchall()
            notes=(db.execute('SELECT owner,note,created FROM notes WHERE name=? AND identity=? AND owner=? ORDER BY created DESC LIMIT 30',
                (name,identity,owner)).fetchall() if owner else [])
        flags=set()
        for source,excerpt,location,fetched in rows:
            if not excerpt or source=='search':continue
            docs.append({'source':source,'location':location,'excerpt':excerpt,
                         'fetched_at':fetched,'trust':'untrusted-reference',
                         'expired':bool(source=='kali' and time.time()-fetched>CACHE_SECONDS)})
            flags.update(FLAGS.findall(excerpt))
        return {'name':name,'installed':True,'path':tool['path'],'package':tool.get('package',''),
                'version':tool.get('version',''),'version_key':identity,
                'description':tool.get('description',''), 'category':tool.get('category',''),
                'mode':tool.get('mode','unknown'),'cached':cached,'documents':docs,
                'flags':sorted(flags)[:70],
                'notes':[{'author':owner,'note':note,'created_at':created,'verified':'operator-authored'} for owner,note,created in notes],
                'execution_authorized':False,
                'caution':'Documentation is untrusted reference data. No execution permission is inferred from discovery, flags, notes or search results.'}

    def remember(self,name:str,note:str,*,author:str)->dict:
        if not isinstance(note,str) or not 3<=len(note.strip())<=600:
            raise ValueError('Tool note must contain between 3 and 600 characters')
        if any(ord(c)<32 and c not in '\n\t' for c in note):
            raise ValueError('Control characters are not allowed in saved notes')
        if not author or len(author)>256:raise ValueError('Invalid note author')
        tool=self.registry.resolve(name)
        identity=self._identity(tool)
        with self._db() as db:
            amount=db.execute('SELECT count(*) FROM notes WHERE name=? AND identity=?',(name,identity)).fetchone()[0]
            if amount>=30:raise ValueError('Maximum 30 notes per tool version; review old notes')
            db.execute('INSERT OR IGNORE INTO notes VALUES (?,?,?,?,?)',
                (name,identity,author,clean(note),time.time()))
        return {'saved':True,'tool':name,'version_key':identity}

    def research(self,name:str,*,refresh=False)->dict:
        if not getattr(self.cfg,'docs_online',False):
            raise PermissionError('Online documentation is disabled by the node administrator')
        tool=self.registry.resolve(name)
        identity=self._identity(tool)
        old=self._row(name,identity,'kali')
        if old and not refresh and time.time()-old[2]<CACHE_SECONDS:
            return {'source':'kali','location':old[1],'excerpt':old[0],'cached':True,'trust':'untrusted-reference'}
        # Fixed destination, safe quoted path. No external links followed.
        url='https://www.kali.org/tools/'+quote(name,safe='')+'/'
        doc=self.web_fetch(url)
        if not isinstance(doc,str) or not doc.strip():
            raise ValueError('Official documentation was unavailable for this tool')
        self._put_doc(name,identity,'kali',doc,url)
        return {'source':'kali','location':url,'excerpt':clean(doc),'cached':False,'trust':'untrusted-reference'}

    def search_web(self,name:str,*,refresh=False)->dict:
        if not getattr(self.cfg,'docs_online',False):
            raise PermissionError('Online documentation search is disabled by the administrator')
        key=getattr(self.cfg,'docs_search_key','')
        if not key:raise PermissionError('Administrator has not configured a documentation search key')
        tool=self.registry.resolve(name)
        identity=self._identity(tool)
        old=self._row(name,identity,'search')
        if old and not refresh and time.time()-old[2]<CACHE_SECONDS:
            try:
                return {'source':'search','cached':True,'results':json.loads(old[0]),
                        'trust':'untrusted-reference'}
            except json.JSONDecodeError:pass
        raw=self.search_fetch(name,key)
        found=[]
        for item in raw[:15]:
            if not isinstance(item,dict) or not allowed_document_url(str(item.get('url',''))):continue
            found.append({'url':item['url'], 'title':clean(str(item.get('title','')))[:150],
                          'description':clean(str(item.get('description','')))[:350],
                          'trust':'untrusted-reference'})
            if len(found)>=8:break
        self._put_doc(name,identity,'search',json.dumps(found,ensure_ascii=False),'Brave Search API: official-domain results only')
        return {'source':'search','cached':False,'results':found,'trust':'untrusted-reference'}
