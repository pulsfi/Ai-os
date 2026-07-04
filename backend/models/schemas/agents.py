"""Agents API contracts — read-only vault-backed pipeline state."""

from datetime import datetime

from pydantic import BaseModel


class AgentReport(BaseModel):
    """One dated entry from an agent's Reports.md (the 'log' unit)."""

    title: str
    date: str  # ISO date as written in the vault heading
    body: str


class AgentSummary(BaseModel):
    """Status-card view of one agent."""

    name: str
    status: str  # from vault frontmatter: active | paused | unknown
    created: str | None = None
    description: str = ""
    report_count: int = 0
    last_report_date: str | None = None
    last_activity: datetime | None = None


class AgentDetail(AgentSummary):
    """Full agent view: summary + the markdown sections."""

    mission: str = ""
    rules: str = ""
    tasks: str = ""


class AgentControlResult(BaseModel):
    """Honest response to start/stop/restart requests.

    There is no process runtime yet (Stage 6 gate) — `accepted` is False
    and `reason` explains why, instead of faking a state change.
    """

    agent: str
    action: str
    accepted: bool
    reason: str
