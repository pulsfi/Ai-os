"""Agents API contracts — read-only vault-backed pipeline state."""

from datetime import datetime

from pydantic import BaseModel


class AgentReport(BaseModel):
    """One dated entry from an agent's Reports.md (the 'log' unit)."""

    title: str
    date: str  # ISO date as written in the vault heading
    body: str


class AgentSummary(BaseModel):
    """Status-card view of one agent (vault state + live runtime state)."""

    name: str
    status: str  # from vault frontmatter: active | paused | unknown
    created: str | None = None
    description: str = ""
    report_count: int = 0
    last_report_date: str | None = None
    last_activity: datetime | None = None
    # --- live runtime (Stage 6) ---
    runtime_state: str = "unknown"  # running | idle | stopped | error | unknown
    last_run: str | None = None
    last_summary: str | None = None
    last_ok: bool | None = None
    cycles: int = 0


class AgentDetail(AgentSummary):
    """Full agent view: summary + the markdown sections."""

    mission: str = ""
    rules: str = ""
    tasks: str = ""


class AgentControlResult(BaseModel):
    """Response to start/stop/restart — a real runtime state change (Stage 6)."""

    agent: str
    action: str
    accepted: bool
    reason: str
    runtime_state: str = "unknown"


class AgentTick(BaseModel):
    """One agent's output from a single pipeline cycle."""

    agent: str
    ts: str
    ok: bool
    summary: str
    detail: str = ""


class RuntimeAgentStatus(BaseModel):
    """Live runtime view of one agent."""

    name: str
    enabled: bool
    runtime_state: str  # running | idle | stopped | error
    runs: int
    last_run: str | None = None
    last_summary: str | None = None
    last_ok: bool | None = None


class RuntimeStatus(BaseModel):
    """The whole pipeline runtime: cadence, cycles, per-agent state, feed."""

    running: bool
    cycle_seconds: float
    cycles: int
    started_at: str | None
    agents: list[RuntimeAgentStatus]
    recent: list[AgentTick]
