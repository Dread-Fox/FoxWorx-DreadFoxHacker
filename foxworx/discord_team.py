"""Discord team intelligence: opt-in, channel-scoped, evidence *summaries* only.

Discord messages are untrusted observations, never commands, permissions or
verified scope. The bot token stays server-side. No Gateway or user tokens.
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from .ai import redact

LOGGER = logging.getLogger(__name__)
CHANNEL = re.compile(r'[0-9]{15,22}\Z')
TEAM_KEY = re.compile(r'[a-z0-9][a-z0-9_-]{2,47}\Z')
MARKER = '[FOXWORX-FINDING:v1]'
TAG = re.compile(r'(?im)^\s*\[fx:([a-z0-9][a-z0-9_-]{2,47})\]\s*$')
MAX_ITEMS = 50
MAX_CONTENT = 1400


def clean(value: str, limit: int = MAX_CONTENT) -> str:
    """Reduce accidental credential disclosure, log injections and pings."""
    s = redact(value or '')
    s = re.sub(r'(?i)\b(bot\s+[a-zA-Z0-9_\-.]{18,}|gh[pousr]_[a-zA-Z0-9]{20,}|discord(?:[_. -]?(?:bot[_. -]?)?token)?\s*[:=]\s*\S+)', '[REDACTED_CREDENTIAL]', s)
    s = re.sub(r'(?i)\b(?:sk-[a-zA-Z0-9_-]{10,}|AIza[a-zA-Z0-9_-]{25,})\b', '[REDACTED_KEY]', s)
    s = re.sub(r'<@!?\d+>|<@&\d+>|<#[0-9]+>|@everyone|@here', '[mention removed]', s, flags=re.I)
    s = ''.join(c for c in s if (c in '\n\t' or ord(c) >= 32) and c != '\x7f')
    return s.strip()[:limit]


def extract_tag(content: str) -> tuple[str, str]:
    """Parse trusted wire *format*, not truth of a Discord author's claims."""
    if content.startswith(MARKER + '\n'):
        try:
            obj = json.loads(content[len(MARKER)+1:])
            if isinstance(obj, dict) and TEAM_KEY.fullmatch(obj.get('team_key','')):
                return obj['team_key'], clean((str(obj.get('title',''))+' — '+str(obj.get('finding',''))).strip(' —'), MAX_CONTENT)
        except (ValueError, TypeError):
            pass
    m = TAG.search(content)
    if m:
        body=TAG.sub('',content)
        body=body.replace(MARKER,'').strip()
        return m.group(1), clean(body, MAX_CONTENT)
    return '', clean(content, MAX_CONTENT)


class DiscordTeam:
    def __init__(self, cfg, store, transport=None):
        self.cfg, self.store = cfg, store
        self.token = cfg.discord_bot_token
        self.channel = cfg.discord_channel_id
        self.guild = cfg.discord_guild_id
        self.base = 'https://discord.com/api/v10'
        self.client = httpx.AsyncClient(timeout=12, transport=transport, follow_redirects=False, trust_env=False)
        self.poll_task = None
        self.lock = asyncio.Lock()
        self.last_error = ''
        self.last_poll = 0
        self.last_sent = 0
        self.cooldown_until = 0.0

    @property
    def enabled(self):
        return bool(self.token and self.channel)

    def status(self):
        return {'configured':self.enabled,'channel_id':self.channel if self.enabled else '',
                'guild_id':self.guild if self.enabled else '', 'poll_seconds':self.cfg.discord_poll_seconds,
                'agent_drafts_enabled':self.enabled, 'automatic_agent_posting':False,
                'last_poll':self.last_poll,'last_error':self.last_error[:220]}

    async def start(self):
        if self.enabled:
            self.poll_task=asyncio.create_task(self._run(),name='foxworx-discord-poller')

    async def shutdown(self):
        if self.poll_task:
            self.poll_task.cancel()
            await asyncio.gather(self.poll_task,return_exceptions=True)
        await self.client.aclose()

    async def _run(self):
        while True:
            try:
                await self.sync()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error='Discord polling unavailable (check token, channel permissions, Message Content access and connectivity)'
                LOGGER.warning('Discord team polling failed: %s', type(exc).__name__)
            await asyncio.sleep(self.cfg.discord_poll_seconds)

    async def _request(self, method, path, *, params=None, payload=None):
        if not self.enabled:
            raise HTTPException(503,'Discord integration is not configured on this node')
        if time.monotonic() < self.cooldown_until:
            raise HTTPException(429,'Discord rate limit: retry later')
        try:
            r=await self.client.request(method,self.base+path,params=params,json=payload,
                headers={'Authorization':'Bot '+self.token,'User-Agent':'FOXWORX-DiscordBridge/1.0'})
        except httpx.HTTPError as exc:
            raise HTTPException(502,'Discord network unavailable') from exc
        if r.status_code==429:
            try: wait=min(60,max(1,float(r.json().get('retry_after',5))))
            except (ValueError,TypeError):wait=5
            self.cooldown_until=time.monotonic()+wait
            raise HTTPException(429,'Discord API rate limited; retry after cooldown')
        if r.status_code in (401,403,404):
            raise HTTPException(502, 'Discord authentication, channel, or channel permission check failed')
        if r.status_code >= 400:
            raise HTTPException(502,'Discord rejected the request')
        try:return r.json()
        except ValueError as exc:raise HTTPException(502,'Unexpected Discord response') from exc

    def _cursor_owner(self):
        return 'discord-bridge:'+self.channel

    def _cursor(self):
        return self.store.get('discord_cursor','current',self._cursor_owner())

    @staticmethod
    def _parse_message(item, channel, guild):
        if not isinstance(item,dict) or not CHANNEL.fullmatch(str(item.get('id',''))):
            return None
        if str(item.get('channel_id',''))!=channel:
            return None
        if guild and str(item.get('guild_id','')) not in ('',guild):
            return None
        content=str(item.get('content',''))[:6000]
        team_key, body=extract_tag(content)
        if not body or not team_key:return None  # Never store ordinary untagged channel chat.
        author=item.get('author') or {}
        return {'id':str(item['id']),'channel_id':channel,'guild_id':str(item.get('guild_id','')),
                'team_key':team_key,'author':clean(str(author.get('global_name') or author.get('username') or 'Discord member'),80),
                'author_bot':bool(author.get('bot')),'content':body,'origin':'discord-untrusted',
                'timestamp':str(item.get('timestamp',''))[:40],
                'url':f'https://discord.com/channels/{guild or item.get("guild_id") or "@me"}/{channel}/{item["id"]}'}

    async def sync(self):
        """Ingest recent messages once; never let Discord content control local execution."""
        async with self.lock:
            cursor=self._cursor()
            args={'limit':100}
            if cursor and cursor.get('last_id'):
                args['after']=cursor['last_id']
            # Fetch at most 100 per pass; catch up with repeated polls rather than
            # skipping beyond first page when a channel is busy.
            records=await self._request('GET',f'/channels/{self.channel}/messages',params=args)
            if not isinstance(records,list):
                raise HTTPException(502,'Discord returned an invalid message list')
            processed=0
            last=cursor.get('last_id','') if cursor else ''
            for item in sorted(records,key=lambda m:int(m.get('id','0')) if str(m.get('id','')).isdigit() else 0):
                parsed=self._parse_message(item,self.channel,self.guild)
                if parsed:
                    self.store.put('discord_message',self._cursor_owner(),parsed)
                    processed+=1
                msg_id=str(item.get('id',''))
                if CHANNEL.fullmatch(msg_id) and (not last or int(msg_id)>int(last)):
                    last=msg_id
            # Restrict retained channel data to recent history; no indefinite cache.
            with self.store.db() as c:
                c.execute('''DELETE FROM records WHERE kind='discord_message' AND owner=?
                    AND id NOT IN (SELECT id FROM records WHERE kind='discord_message' AND owner=?
                    ORDER BY CAST(json_extract(data,'$.id') AS INTEGER) DESC LIMIT 1000)''',
                    (self._cursor_owner(), self._cursor_owner()))
            if last:
                self.store.put('discord_cursor',self._cursor_owner(),{'id':'current','last_id':last})
            self.last_poll=int(time.time());self.last_error=''
            return {'received':processed,'last_poll':self.last_poll}

    def messages(self, owner, engagement, limit=40):
        team_key=engagement.get('team_key','')
        if not self.enabled or not TEAM_KEY.fullmatch(team_key):
            return []
        # Filtering in SQLite ensures plain, untagged posts never enter another
        # engagement's AI context. They remain available in Discord itself.
        with self.store.db() as c:
            rows=c.execute("SELECT data FROM records WHERE kind='discord_message' AND owner=? AND json_extract(data,'$.team_key')=? ORDER BY CAST(json_extract(data,'$.id') AS INTEGER) DESC LIMIT ?",
                (self._cursor_owner(),team_key,min(MAX_ITEMS,max(1,int(limit))))).fetchall()
        return [json.loads(r['data']) for r in reversed(rows)]

    def intelligence(self, owner, engagement, limit=12):
        return [{'author':m['author'],'content':m['content'][:650],'timestamp':m['timestamp'],
                 'discord_link':m['url'],'verification':'UNTRUSTED, NOT VALIDATED'}
                for m in self.messages(owner,engagement,limit)]

    def _engagement(self, owner, engagement_id):
        engagement=self.store.get('engagement',engagement_id,owner)
        if not engagement:raise HTTPException(404,'Engagement not found')
        if not TEAM_KEY.fullmatch(engagement.get('team_key','')):
            raise HTTPException(409,'Set a matching team key in Engagement scope before using Discord')
        return engagement

    def draft(self, owner, engagement_id, title, finding, source='operator', job_id=''):
        engagement=self._engagement(owner,engagement_id)
        if not self.enabled:raise HTTPException(503,'Discord integration is not configured')
        if job_id:
            job=self.store.get('job',job_id,owner)
            if not job or job.get('engagement_id')!=engagement_id:
                raise HTTPException(404,'Job is not part of this engagement')
        if source not in ('operator','agent'):
            raise HTTPException(422,'Invalid finding source')
        title=clean(title,100)
        finding=clean(finding,MAX_CONTENT)
        if not title or len(finding)<3:
            raise HTTPException(422,'A title and finding are required')
        record=self.store.put('discord_draft',owner,{
            'engagement_id':engagement_id,'team_key':engagement['team_key'],'title':title,
            'finding':finding,'source':source,'job_id':job_id,
            'status':'awaiting-approval','posted_id':'', 'created_at':int(time.time())})
        self.store.event(owner,'discord-draft',record['id'])
        return record

    def drafts(self, owner, engagement_id):
        self._engagement(owner,engagement_id)
        return [d for d in self.store.list('discord_draft',owner,100,engagement_id=engagement_id)]

    async def publish(self, owner, engagement_id, draft_id, approved):
        eng=self._engagement(owner,engagement_id)
        draft=self.store.get('discord_draft',draft_id,owner)
        if not draft or draft['engagement_id']!=engagement_id or draft['team_key']!=eng['team_key']:
            raise HTTPException(404,'Draft not found in this engagement')
        if draft['status']!='awaiting-approval':
            raise HTTPException(409,'Draft has already been acted upon')
        if approved is not True:
            draft['status']='rejected';self.store.put('discord_draft',owner,draft)
            self.store.event(owner,'discord-draft-rejected',draft_id)
            return draft
        # Human review is mandatory; the model cannot invoke this method.
        # Reserve draft before any network call to prevent duplicate publish.
        draft['status']='sending';self.store.put('discord_draft',owner,draft)
        # Human-readable Discord post plus a machine-readable engagement tag.
        # Never attach raw logs or embed other servers' resources.
        msg=(f'**FOXWORX finding: {draft["title"]}**\n'
             f'[fx:{draft["team_key"]}]\n\n{draft["finding"]}\n\n'
             f'_{self.cfg.discord_node_label} · {"Agent draft" if draft["source"]=="agent" else "Operator summary"}_\n'
             f'{MARKER}')
        if len(msg)>1900:
            draft['status']='awaiting-approval';self.store.put('discord_draft',owner,draft)
            raise HTTPException(422,'Draft too long for Discord; shorten it before sharing')
        try:
            result=await self._request('POST',f'/channels/{self.channel}/messages',payload={
                'content':msg,'allowed_mentions':{'parse':[]}})
        except Exception:
            # Do not automatically retry an uncertain send: Discord may have received it.
            draft['status']='delivery-unknown';self.store.put('discord_draft',owner,draft)
            self.store.event(owner,'discord-delivery-unconfirmed',draft_id)
            raise
        if not isinstance(result,dict) or not CHANNEL.fullmatch(str(result.get('id',''))):
            draft['status']='delivery-unknown';self.store.put('discord_draft',owner,draft)
            raise HTTPException(502,'Discord response did not confirm message ID')
        draft['status']='published';draft['posted_id']=str(result['id'])
        self.store.put('discord_draft',owner,draft)
        self.store.event(owner,'discord-published',draft_id)
        return draft
