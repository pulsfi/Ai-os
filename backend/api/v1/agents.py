"""Agents endpoints (Stage 6) — the 7-agent pipeline, live.

Vault markdown remains the human-readable source of truth for each
agent's mission/rules/reports; the runtime overlays live state (what the
agent is doing right now) and the control endpoints really start/stop the
agents in the running pipeline.
"""

from typing import Literal

from fastapi import APIRouter

from core.dependencies import AgentRuntimeDep, AgentsServiceDep
from core.exceptions import NotFoundError
from models.schemas.agents import (
    AgentControlResult,
    AgentDetail,
    AgentReport,
    AgentSummary,
    AgentTick,
    RuntimeStatus,
)

router = APIRouter()


def _merge_runtime(summary: AgentSummary, runtime: AgentRuntimeDep) -> AgentSummary:
    rt = runtime.agent_runtime(summary.name)
    if rt is not None:
        summary.runtime_state = rt.runtime_state
        summary.last_run = rt.last_run
        summary.last_summary = rt.last_summary
        summary.last_ok = rt.last_ok
        summary.cycles = rt.runs
    return summary


def _summary_from_runtime(runtime: AgentRuntimeDep) -> list[AgentSummary]:
    """Build the agent list from the live runtime alone — used when the vault
    markdown isn't present (e.g. the Docker image ships without it)."""
    return [
        AgentSummary(
            name=rt.name,
            status="active" if rt.enabled else "paused",
            description=rt.last_summary or "Live pipeline agent.",
            runtime_state=rt.runtime_state,
            last_run=rt.last_run,
            last_summary=rt.last_summary,
            last_ok=rt.last_ok,
            cycles=rt.runs,
        )
        for rt in runtime.status().agents
    ]


@router.get("", response_model=list[AgentSummary])
async def list_agents(
    agents: AgentsServiceDep, runtime: AgentRuntimeDep
) -> list[AgentSummary]:
    """Every agent: vault status + live runtime state. Falls back to the
    live runtime when the vault markdown isn't available on this host."""
    vault_agents = agents.list_agents()
    if vault_agents:
        return [_merge_runtime(s, runtime) for s in vault_agents]
    return _summary_from_runtime(runtime)


@router.get("/runtime", response_model=RuntimeStatus)
async def runtime_status(runtime: AgentRuntimeDep) -> RuntimeStatus:
    """The whole pipeline: cadence, cycles, per-agent state, live feed."""
    return runtime.status()


@router.get("/{name}", response_model=AgentDetail)
async def agent_detail(
    name: str, agents: AgentsServiceDep, runtime: AgentRuntimeDep
) -> AgentDetail:
    """One agent's full state: mission, rules, tasks, live runtime."""
    try:
        detail = agents.get_agent(name)
    except NotFoundError:
        # No vault markdown on this host — synthesize from the live runtime.
        rt = runtime.agent_runtime(name)
        if rt is None:
            raise
        detail = AgentDetail(
            name=rt.name,
            status="active" if rt.enabled else "paused",
            description=rt.last_summary or "Live pipeline agent.",
            mission="(vault notes not available on this server)",
        )
    rt = runtime.agent_runtime(detail.name)
    if rt is not None:
        detail.runtime_state = rt.runtime_state
        detail.last_run = rt.last_run
        detail.last_summary = rt.last_summary
        detail.last_ok = rt.last_ok
        detail.cycles = rt.runs
    return detail


@router.get("/{name}/reports", response_model=list[AgentReport])
async def agent_reports(name: str, agents: AgentsServiceDep) -> list[AgentReport]:
    """The agent's report log from the vault, newest first."""
    return agents.get_reports(name)


@router.get("/{name}/activity", response_model=list[AgentTick])
async def agent_activity(name: str, runtime: AgentRuntimeDep) -> list[AgentTick]:
    """The agent's live pipeline output, newest first."""
    if not runtime.has(name):
        raise NotFoundError(f"Unknown agent: {name}")
    return runtime.recent_for(name)


@router.post("/{name}/{action}", response_model=AgentControlResult)
async def control_agent(
    name: str,
    action: Literal["start", "stop", "restart"],
    runtime: AgentRuntimeDep,
) -> AgentControlResult:
    """Really start/stop/restart an agent in the live pipeline (Stage 6)."""
    if not runtime.has(name):
        raise NotFoundError(f"Unknown agent: {name}")
    accepted, reason, state = runtime.control(name, action)
    return AgentControlResult(
        agent=name, action=action, accepted=accepted, reason=reason, runtime_state=state
    )
