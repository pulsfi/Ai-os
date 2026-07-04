"""Agents endpoints — read-only pipeline state from the vault.

The control endpoint exists so the frontend has a real, typed contract —
but it honestly reports that no runtime exists yet (Stage 6 gate) instead
of faking a process state change.
"""

from typing import Literal

from fastapi import APIRouter

from core.dependencies import AgentsServiceDep
from models.schemas.agents import (
    AgentControlResult,
    AgentDetail,
    AgentReport,
    AgentSummary,
)

router = APIRouter()


@router.get("", response_model=list[AgentSummary])
async def list_agents(agents: AgentsServiceDep) -> list[AgentSummary]:
    """All agents in pipeline order with vault-derived status."""
    return agents.list_agents()


@router.get("/{name}", response_model=AgentDetail)
async def agent_detail(name: str, agents: AgentsServiceDep) -> AgentDetail:
    """One agent's full state: mission, rules, tasks, activity."""
    return agents.get_agent(name)


@router.get("/{name}/reports", response_model=list[AgentReport])
async def agent_reports(name: str, agents: AgentsServiceDep) -> list[AgentReport]:
    """The agent's report log, newest first."""
    return agents.get_reports(name)


@router.post("/{name}/{action}", response_model=AgentControlResult)
async def control_agent(
    name: str,
    action: Literal["start", "stop", "restart"],
    agents: AgentsServiceDep,
) -> AgentControlResult:
    """Accept a control request — honestly declined until Stage 6.

    404s for unknown agents; for known agents returns accepted=False with
    the reason, so the UI can show the real system state.
    """
    agents.get_agent(name)  # validates the agent exists (404 otherwise)
    return AgentControlResult(
        agent=name,
        action=action,
        accepted=False,
        reason=(
            "Agent runtime is not available yet: the multi-agent automation "
            "stage (Stage 6) has not been opened. Agents currently run via "
            "the vault + automation scripts, not as managed processes."
        ),
    )
