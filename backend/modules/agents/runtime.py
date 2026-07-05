"""Agent runtime (Stage 6) — the 7-agent pipeline, running live.

Each agent is a thin orchestrator over the REAL modules already built:
it queries live data / live system state and emits a real result. There
is no invented cognition here — the "intelligence" is the pipeline wiring
that turns the vault's 7-agent concept into a working control loop.

Pipeline order (a shared context is threaded through each pass):
  Research → Strategy → Risk → Execution → Monitoring → Learning → Documentation

Everything the agents observe is real; nothing they do moves money. The
Execution agent only REPORTS execution state — the live-trading gate and
the human-approval wallet path are unchanged.
"""

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import Settings
from core.exceptions import AppError
from models.schemas.agents import (
    AgentTick,
    RuntimeAgentStatus,
    RuntimeStatus,
)
from modules.bots.manager import get_bot_manager
from modules.execution.readiness import evaluate_readiness
from modules.execution.risk_engine import get_risk_engine
from modules.market import get_market_manager
from modules.market.pumpfun import get_pumpfun_client

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class _Ctx:
    """Blackboard shared across one pipeline pass."""

    data: dict = field(default_factory=dict)


@dataclass
class _Result:
    ok: bool
    summary: str
    detail: str = ""


# One agent = a name + an async job over the live modules.
JobFn = Callable[["AgentRuntime", _Ctx], Awaitable[_Result]]


@dataclass
class _Agent:
    name: str
    job: JobFn
    enabled: bool = True
    runs: int = 0
    last_run: str | None = None
    last_summary: str | None = None
    last_ok: bool | None = None

    def runtime_state(self, loop_running: bool) -> str:
        if not self.enabled:
            return "stopped"
        if self.last_ok is False:
            return "error"
        if loop_running and self.last_run is not None:
            return "running"
        return "idle"


# --- the seven agent jobs (real work over real modules) ----------------------


async def _research(rt: "AgentRuntime", ctx: _Ctx) -> _Result:
    """Discover fresh pump.fun launches (the top of the funnel)."""
    coins = await rt._pumpfun.get_new_coins(limit=8)
    ctx.data["new_launches"] = len(coins)
    if not coins:
        return _Result(True, "no new launches surfaced this cycle")
    top = coins[0]
    names = ", ".join(c.symbol or c.mint[:4] for c in coins[:5])
    return _Result(
        True,
        f"{len(coins)} new launches — newest {top.symbol or top.mint[:6]}",
        f"top: {names}",
    )


async def _strategy(rt: "AgentRuntime", ctx: _Ctx) -> _Result:
    """Read the live bot fleet — which strategies are active + exposure."""
    statuses = rt._bots.statuses()
    running = [s for s in statuses if s.state.value == "running"]
    open_pos = sum(s.open_positions for s in statuses)
    ctx.data["bots_running"] = len(running)
    ctx.data["open_positions"] = open_pos
    names = ", ".join(s.config.id for s in running) or "none"
    return _Result(
        True,
        f"{len(running)}/{len(statuses)} bots active, {open_pos} open positions",
        f"running: {names}",
    )


async def _risk(rt: "AgentRuntime", ctx: _Ctx) -> _Result:
    """Report the risk posture — limits, daily PnL, kill switch."""
    risk = rt._risk
    ctx.data["kill_switch"] = risk.kill_switch
    state = "HALTED (kill switch)" if risk.kill_switch else ("armed" if risk.armed else "disarmed")
    return _Result(
        True,
        f"risk {state}; today ${risk.realized_today:.2f} / -${risk.limits.daily_loss_limit_usd:.0f} limit",
        f"max ${risk.limits.max_position_usd:.0f}/order, "
        f"{risk.limits.max_concurrent_positions} concurrent, "
        f"{risk.limits.max_slippage_bps / 100:.1f}% slippage",
    )


async def _execution(rt: "AgentRuntime", ctx: _Ctx) -> _Result:
    """Report execution state — it never trades; the gate is unchanged."""
    risk = rt._risk
    if risk.kill_switch:
        return _Result(True, "execution halted (kill switch engaged)")
    mode = "dry-run only (no live path wired)"
    gate = "armed" if risk.armed else "disarmed"
    return _Result(
        True,
        f"execution {gate}, {mode}",
        "autonomous live trading stays gated; real trades need a human Phantom click",
    )


async def _monitoring(rt: "AgentRuntime", ctx: _Ctx) -> _Result:
    """Watch data-provider health and flag degradation."""
    status = rt._market.status()
    healthy = [p for p in status.providers if p.errors == 0 or p.last_success]
    degraded = [p.name for p in status.providers if p.errors > 0 and not p.last_success]
    ctx.data["providers_ok"] = len(healthy)
    if degraded:
        return _Result(
            True,
            f"{len(healthy)}/{len(status.providers)} providers healthy; watch: {', '.join(degraded)}",
            f"cache: {status.cache_backend}",
        )
    return _Result(
        True,
        f"all {len(status.providers)} data providers healthy",
        f"cache: {status.cache_backend}, {status.tracked_tokens} tokens tracked",
    )


async def _learning(rt: "AgentRuntime", ctx: _Ctx) -> _Result:
    """Analyze the paper track record and extract the current lesson."""
    perf = rt._bots.performance()
    fleet = next((p for p in perf if p.bot_id == "fleet"), None)
    bots = [p for p in perf if p.bot_id != "fleet" and p.closed_trades > 0]
    if not fleet or fleet.closed_trades == 0:
        return _Result(True, "no closed trades yet — nothing to learn from")
    best = max(bots, key=lambda p: p.realized_pnl_usd, default=None)
    worst = min(bots, key=lambda p: p.realized_pnl_usd, default=None)
    ctx.data["fleet_win_rate"] = fleet.win_rate_pct
    lesson = ""
    if best and worst and best.bot_id != worst.bot_id:
        lesson = f"best: {best.name} (${best.realized_pnl_usd:+.2f}); worst: {worst.name} (${worst.realized_pnl_usd:+.2f})"
    return _Result(
        True,
        f"fleet {fleet.win_rate_pct}% win over {fleet.closed_trades} closed, ${fleet.realized_pnl_usd:+.2f}",
        lesson,
    )


async def _documentation(rt: "AgentRuntime", ctx: _Ctx) -> _Result:
    """Summarize the cycle for the record (the scheduler does the vault write)."""
    parts = []
    if "new_launches" in ctx.data:
        parts.append(f"{ctx.data['new_launches']} launches")
    if "bots_running" in ctx.data:
        parts.append(f"{ctx.data['bots_running']} bots")
    if "open_positions" in ctx.data:
        parts.append(f"{ctx.data['open_positions']} open")
    if ctx.data.get("fleet_win_rate") is not None:
        parts.append(f"{ctx.data['fleet_win_rate']}% win")
    return _Result(
        True,
        "cycle logged: " + (", ".join(parts) if parts else "quiet cycle"),
        "daily note is written by the report scheduler at the configured hour",
    )


# Vault agent name -> live job. Order defines the pipeline.
_PIPELINE: list[tuple[str, JobFn]] = [
    ("Research Agent", _research),
    ("Strategy Agent", _strategy),
    ("Risk Agent", _risk),
    ("Execution Agent", _execution),
    ("Monitoring Agent", _monitoring),
    ("Learning Agent", _learning),
    ("Documentation Agent", _documentation),
]


class AgentRuntime:
    """Runs the 7-agent pipeline as a live loop over the real modules."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cycle_s = settings.agents_cycle_seconds
        self._agents = {name: _Agent(name, job) for name, job in _PIPELINE}
        self._recent: deque[AgentTick] = deque(maxlen=60)
        self._task: asyncio.Task[None] | None = None
        self._started_at: str | None = None
        self.cycles = 0
        # Live module singletons (constructed lazily by their own getters).
        self._pumpfun = get_pumpfun_client(settings)
        self._bots = get_bot_manager(settings)
        self._risk = get_risk_engine(settings)
        self._market = get_market_manager(settings)

    # -- lifecycle ---------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._started_at = _now()
        self._task = asyncio.create_task(self._run(), name="agent-runtime")
        logger.info("agent runtime started (cycle=%.0fs)", self._cycle_s)

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _run(self) -> None:
        while True:
            await self.run_cycle()
            await asyncio.sleep(self._cycle_s)

    async def run_cycle(self) -> None:
        """One full pass through the enabled agents (public for tests)."""
        ctx = _Ctx()
        for agent in self._agents.values():
            if not agent.enabled:
                continue
            try:
                result = await agent.job(self, ctx)
            except AppError as exc:
                result = _Result(False, f"error: {exc.message}")
            except Exception as exc:  # noqa: BLE001 — one agent must not stop the loop
                result = _Result(False, f"error: {type(exc).__name__}: {exc}")
            agent.runs += 1
            agent.last_run = _now()
            agent.last_summary = result.summary
            agent.last_ok = result.ok
            self._recent.appendleft(
                AgentTick(
                    agent=agent.name,
                    ts=agent.last_run,
                    ok=result.ok,
                    summary=result.summary,
                    detail=result.detail,
                )
            )
        self.cycles += 1

    # -- control -----------------------------------------------------------

    def has(self, name: str) -> bool:
        return name in self._agents

    def control(self, name: str, action: str) -> tuple[bool, str, str]:
        """start | stop | restart one agent. Returns (accepted, reason, state)."""
        agent = self._agents.get(name)
        if agent is None:
            return False, f"unknown agent: {name}", "unknown"
        if action == "stop":
            changed = agent.enabled
            agent.enabled = False
            reason = "Agent paused — it will skip pipeline cycles." if changed else "Agent was already stopped."
        elif action == "start":
            changed = not agent.enabled
            agent.enabled = True
            reason = "Agent resumed in the live pipeline." if changed else "Agent was already running."
        else:  # restart
            agent.enabled = True
            agent.last_ok = None
            changed = True
            reason = "Agent restarted; it re-enters the next cycle clean."
        return changed, reason, agent.runtime_state(self.running)

    # -- reporting ----------------------------------------------------------

    def agent_runtime(self, name: str) -> RuntimeAgentStatus | None:
        agent = self._agents.get(name)
        if agent is None:
            return None
        return RuntimeAgentStatus(
            name=agent.name,
            enabled=agent.enabled,
            runtime_state=agent.runtime_state(self.running),
            runs=agent.runs,
            last_run=agent.last_run,
            last_summary=agent.last_summary,
            last_ok=agent.last_ok,
        )

    def status(self) -> RuntimeStatus:
        return RuntimeStatus(
            running=self.running,
            cycle_seconds=self._cycle_s,
            cycles=self.cycles,
            started_at=self._started_at,
            agents=[self.agent_runtime(n) for n in self._agents],  # type: ignore[misc]
            recent=list(self._recent)[:40],
        )

    def recent_for(self, name: str, limit: int = 15) -> list[AgentTick]:
        return [t for t in self._recent if t.agent == name][:limit]


_runtime: AgentRuntime | None = None


def get_agent_runtime(settings: Settings) -> AgentRuntime:
    """Process-wide singleton, same pattern as the other modules."""
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime(settings)
    return _runtime


async def close_agent_runtime() -> None:
    global _runtime
    if _runtime is not None:
        await _runtime.stop()
        _runtime = None
