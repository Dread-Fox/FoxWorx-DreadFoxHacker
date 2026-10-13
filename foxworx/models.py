from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .scope import validate_rule

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Login(StrictModel):
    token: str = Field(min_length=1, max_length=256)
    remember: bool = False

class Engagement(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    include: list[str] = Field(min_length=1, max_length=100)
    exclude: list[str] = Field(default_factory=list, max_length=100)
    notes: str = Field(default='', max_length=6000)
    program_url: str = Field(default='', max_length=1000)
    team_key: str = Field(default='', max_length=48)
    @field_validator('team_key')
    @classmethod
    def valid_team_key(cls, value):
        import re
        if value and not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,47}',value):
            raise ValueError('Team key must be 3–48 lowercase letters, digits, underscores or hyphens')
        return value
    @field_validator('include', 'exclude')
    @classmethod
    def rules(cls, value):
        return list(dict.fromkeys(validate_rule(x) for x in value))

class ProposalSpec(StrictModel):
    engagement_id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=150)
    args: list[str] = Field(default_factory=list, max_length=64)
    profile: Literal['advanced', 'tcp-connect', 'http-headers', 'dns-a', 'whois','tcp-web','http-options','dns-aaaa','dns-mx','dns-txt','dns-caa','dns-ns','dns-soa','dns-cname','tls-certificate','http-status','http-get-limited','web-fingerprint'] = 'advanced'
    target: str = Field(default='', max_length=2048)
    reason: str = Field(default='', max_length=2000)
    interface_name: str = Field(default='', max_length=15)

    @field_validator('args')
    @classmethod
    def arguments(cls, args):
        if any(len(a) > 4096 or '\x00' in a for a in args) or sum(map(len, args)) > 16000:
            raise ValueError('Argument size or NUL-byte limit exceeded')
        return args

class Approval(StrictModel):
    digest: str = Field(min_length=64, max_length=64)
    authorized: bool

class SessionSpec(StrictModel):
    engagement_id: str = Field(min_length=1, max_length=64)

class ChatSpec(StrictModel):
    engagement_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=12000)
    job_id: str | None = Field(default=None, max_length=64)
    share_output: bool = False
    mode: Literal['tutor', 'copilot'] = 'copilot'

class ToolNote(StrictModel):
    note: str = Field(min_length=3,max_length=600)

class ArgumentText(StrictModel):
    text: str = Field(default="", max_length=16000)

class AISelection(StrictModel):
    provider: Literal['openai','codex','anthropic','gemini','xai','deepseek','mistral','ollama','lmstudio','vllm','custom']
    model: str = Field(min_length=1,max_length=160)
    endpoint_id: str = Field(default='',max_length=40)

class AIKeyChange(StrictModel):
    api_key: str = Field(min_length=1,max_length=4096)


class PetName(StrictModel):
    name: str = Field(min_length=1, max_length=40)

class PetCare(StrictModel):
    action: Literal['play','feed','rest']

class PetTracking(StrictModel):
    enabled: bool


class PetContextToggle(StrictModel):
    enabled: bool


class PetChatMessage(StrictModel):
    message: str = Field(min_length=1,max_length=1800)

class PetChatMode(StrictModel):
    mode: Literal['offline','ai']

class PetChatFocus(StrictModel):
    focus: Literal['auto','exploration','craft','wisdom','stewardship']

class RabbitSpec(StrictModel):
    """One explicit, finite authorization grant for a supervised engagement."""
    engagement_id: str = Field(min_length=1, max_length=64)
    objective: str = Field(min_length=8, max_length=4000)
    target: str = Field(min_length=1, max_length=2048)
    execution_mode: Literal['workflows','installed_cli'] = 'workflows'
    profiles: list[str] = Field(default_factory=list, max_length=64)
    max_steps: int = Field(default=8, ge=1, le=10000)
    max_minutes: int = Field(default=15, ge=1, le=1440)
    authorized: bool = False
    @model_validator(mode='before')
    @classmethod
    def mode_defaults(cls, value):
        if isinstance(value,dict) and value.get('execution_mode')=='installed_cli':
            value={**value}
            value.setdefault('max_steps',64)
            value.setdefault('max_minutes',60)
        return value
    @model_validator(mode='after')
    def require_workflows(self):
        if self.execution_mode=='workflows' and not self.profiles:
            raise ValueError('Select at least one workflow')
        return self
    @field_validator('profiles')
    @classmethod
    def unique_profiles(cls, profiles):
        from .command_templates import ID
        if any(not ID.fullmatch(p) or p in ('advanced','shell','command') for p in profiles):
            raise ValueError('Unknown or invalid adapter identifier')
        if len(set(profiles)) != len(profiles):
            raise ValueError('Select each workflow only once')
        return profiles
    @field_validator('target')
    @classmethod
    def valid_target(cls, target):
        from .scope import normalize_target
        return normalize_target(target)


class RabbitMessage(StrictModel):
    message: str = Field(min_length=1,max_length=4000)
    @field_validator('message')
    @classmethod
    def nonempty(cls,value):
        if not value.strip():raise ValueError('Instruction must not be empty')
        return value.strip()


class RegisteredProposalSpec(StrictModel):
    engagement_id: str = Field(min_length=1,max_length=64)
    profile: str = Field(min_length=3,max_length=50)
    target: str = Field(min_length=1,max_length=2048)
    parameters: dict = Field(default_factory=dict,max_length=8)
    reason: str = Field(default='Admin-registered adapter proposal',max_length=500)
    @field_validator('target')
    @classmethod
    def registered_target(cls,value):
        from .scope import normalize_target
        return normalize_target(value)
