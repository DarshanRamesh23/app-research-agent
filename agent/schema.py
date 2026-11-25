from enum import Enum
from pydantic import BaseModel

class Auth(str, Enum):
    oauth2 = "oauth2"; api_key = "api_key"; basic = "basic"
    bearer = "bearer_token"; jwt = "jwt"; none = "none"
    other = "other"; unknown = "unknown"

class Access(str, Enum):
    free_self_serve = "free_self_serve"; free_trial = "free_trial"
    paid_plan = "paid_plan"; admin_approval = "admin_approval"
    partner_gated = "partner_gated"; no_api = "no_api"; unknown = "unknown"

class ApiType(str, Enum):
    rest = "rest"; graphql = "graphql"; both = "both"
    sdk_only = "sdk_only"; cli_only = "cli_only"
    none = "none"; unknown = "unknown"

class Verdict(str, Enum):
    green = "buildable_now"
    yellow = "buildable_with_caveat"
    red = "blocked"
    unknown = "unknown"

class Evidence(BaseModel):
    url: str = ""
    quote: str = ""        # verbatim from the page; empty means value must be "unknown"
    confidence: float = 0.0

class AppRecord(BaseModel):
    id: str
    one_liner: str
    auth_methods: list[Auth]
    access_test: Access     # can a dev get credentials to test?
    access_ship: Access     # can you ship publicly (app review, partner program)?
    api_type: ApiType
    api_breadth: str        # narrow / medium / broad / unknown
    official_mcp: str       # yes / no / community / unknown
    mcp_url: str | None = None
    verdict: Verdict
    blocker: str | None = None
    evidence: dict[str, Evidence] = {}