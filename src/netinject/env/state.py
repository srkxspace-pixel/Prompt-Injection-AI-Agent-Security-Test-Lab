"""In-memory network state. Everything a tool can read or change lives here (DESIGN D2)."""
from pydantic import BaseModel


class Interface(BaseModel):
    description: str = ""
    status: str = "up"  # "up" | "admin-down"


class Device(BaseModel):
    role: str
    mgmt_ip: str
    interfaces: dict[str, Interface] = {}
    acls: dict[str, list[str]] = {}
    routes: dict[str, str] = {}  # prefix -> next hop
    admin_users: list[str] = []
    logging_enabled: bool = True
    syslog_host: str = "10.0.0.50"
    log: list[str] = []


class ScopeEntry(BaseModel):
    """One exact approved change: action (= tool name), device, and the tool's parameters."""
    action: str
    device: str
    params: dict[str, str] = {}


class Comment(BaseModel):
    author: str
    text: str


class Ticket(BaseModel):
    title: str
    status: str  # "approved" | "pending" | "closed"
    scope: list[ScopeEntry] = []  # trusted field: only change control writes it
    description: str = ""
    comments: list[Comment] = []  # untrusted: anyone can comment


class Alert(BaseModel):
    device: str
    severity: str
    summary: str
    details: str = ""
    acknowledged: bool = False


class Runbook(BaseModel):
    title: str
    text: str


class KBArticle(BaseModel):
    title: str
    keywords: list[str] = []
    text: str


class NetworkState(BaseModel):
    devices: dict[str, Device]
    tickets: dict[str, Ticket] = {}
    alerts: dict[str, Alert] = {}
    runbooks: dict[str, Runbook] = {}
    kb: dict[str, KBArticle] = {}
