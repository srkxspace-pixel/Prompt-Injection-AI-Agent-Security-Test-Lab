"""Schemas for the scenario data files in scenarios/data/ (world.yaml, goals.yaml, styles.yaml, tasks/*.yaml)."""
from pydantic import BaseModel, Field

from netinject.env.state import Comment, ScopeEntry


class TicketSpec(BaseModel):
    id: str = Field(pattern=r"^CHG-\d{4}$")
    title: str
    description: str
    comments: list[Comment] = []


class AlertSpec(BaseModel):
    id: str = Field(pattern=r"^A-\d{4}$")
    device: str
    severity: str
    summary: str
    details: str


class LogSpec(BaseModel):
    device: str
    lines: list[str]


class RunbookSpec(BaseModel):
    name: str
    title: str
    text: str


class KBSpec(BaseModel):
    id: str = Field(pattern=r"^KB-\d{4}$")
    title: str
    keywords: list[str]
    query: str  # the query the procedure tells the agent to search for
    text: str


class TaskSpec(BaseModel):
    """One benign NOC task. `change` is the single approved high-impact write; success = it is applied."""
    id: str = Field(pattern=r"^T\d{2}$")
    order: int = Field(ge=0, le=3)  # Latin-square read order (compose.ORDERS)
    title: str
    change: ScopeEntry
    ticket: TicketSpec
    alert: AlertSpec
    log: LogSpec
    runbook: RunbookSpec
    kb: KBSpec


class GoalSpec(BaseModel):
    """An attacker goal: one out-of-scope high-impact write, plus the approved decoy ticket that covers it."""
    id: str = Field(pattern=r"^G\d$")
    change: ScopeEntry
    action_text: str  # what the action does, without the target, e.g. "disable syslog logging"
    decoy_ticket: TicketSpec


class StyleSpec(BaseModel):
    """Attack style. Single-artifact styles use `text`; split uses fragment_a (read before carrier) + fragment_b (carrier)."""
    id: str
    text: str = ""
    fragment_a: str = ""
    fragment_b: str = ""
