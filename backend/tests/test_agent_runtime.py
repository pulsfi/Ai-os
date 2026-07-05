"""Agent runtime tests — a real pipeline cycle over stubbed live modules.

Verifies the 7 agents each produce a real tick, the pipeline is
error-contained (one failing agent doesn't stop the others), and
enable/disable control changes runtime state.
"""

from datetime import datetime, timezone

import pytest

from config import Settings
from models.schemas.bots import BotConfig, BotPerformance, BotState, BotStatus
from modules.agents.runtime import AgentRuntime


class StubPumpFun:
    async def get_new_coins(self, limit: int = 8):
        from modules.market.pumpfun import PumpCoin

        return [
            PumpCoin(
                mint="Mint111", name="Test", symbol="TST",
                created_at=datetime.now(timezone.utc),
                usd_market_cap=12000.0, reply_count=3, complete=False,
                bonding_progress_pct=10.0, is_currently_live=True,
            )
        ]


class StubBots:
    def statuses(self):
        return [
            BotStatus(
                config=BotConfig(
                    id="sniper", name="Launch Sniper", strategy="s", description="d",
                    interval_s=5, usd_per_trade=50, max_open_positions=3,
                    take_profit_pct=40, stop_loss_pct=25, max_hold_s=900,
                ),
                state=BotState.RUNNING, open_positions=2,
            )
        ]

    def performance(self):
        return [
            BotPerformance(
                bot_id="fleet", name="Fleet", closed_trades=10, wins=6, losses=4,
                win_rate_pct=60.0, realized_pnl_usd=12.5,
            ),
            BotPerformance(
                bot_id="sniper", name="Launch Sniper", closed_trades=5, wins=4,
                losses=1, win_rate_pct=80.0, realized_pnl_usd=20.0,
            ),
            BotPerformance(
                bot_id="trend", name="Trend Scalper", closed_trades=5, wins=2,
                losses=3, win_rate_pct=40.0, realized_pnl_usd=-7.5,
            ),
        ]


class StubMarket:
    def status(self):
        from modules.market.market_models import MarketStatus, ProviderStatus

        return MarketStatus(
            providers=[
                ProviderStatus(
                    name="dexscreener", configured=True, calls=5, errors=0,
                    avg_latency_ms=100.0,
                    last_success=datetime.now(timezone.utc), last_error=None,
                )
            ],
            cache_backend="memory", cache_hits=1, cache_misses=1,
            scheduler_enabled=False, scheduler_interval_s=300, scheduler_runs=0,
            last_refresh=None, tracked_tokens=4,
        )


class StubRisk:
    kill_switch = False
    armed = False
    realized_today = 0.0

    class limits:
        max_position_usd = 10.0
        daily_loss_limit_usd = 25.0
        max_concurrent_positions = 2
        max_slippage_bps = 150


def make_runtime() -> AgentRuntime:
    rt = AgentRuntime(Settings(_env_file=None, log_level="WARNING"))
    rt._pumpfun = StubPumpFun()  # type: ignore[assignment]
    rt._bots = StubBots()  # type: ignore[assignment]
    rt._market = StubMarket()  # type: ignore[assignment]
    rt._risk = StubRisk()  # type: ignore[assignment]
    return rt


async def test_full_cycle_produces_ticks_for_all_agents() -> None:
    rt = make_runtime()
    await rt.run_cycle()
    status = rt.status()
    assert status.cycles == 1
    # All seven agents ran and produced an OK tick.
    assert len(status.agents) == 7
    assert all(a.last_ok for a in status.agents)
    # Research saw the launch, Strategy saw the running bot, Learning the record.
    research = rt.agent_runtime("Research Agent")
    assert research is not None and "launch" in research.last_summary.lower()
    learning = rt.agent_runtime("Learning Agent")
    assert learning is not None and "60.0% win" in learning.last_summary


async def test_disabled_agent_skips_but_others_run() -> None:
    rt = make_runtime()
    accepted, _reason, state = rt.control("Research Agent", "stop")
    assert accepted is True and state == "stopped"
    await rt.run_cycle()
    research = rt.agent_runtime("Research Agent")
    assert research is not None and research.runs == 0  # skipped
    strategy = rt.agent_runtime("Strategy Agent")
    assert strategy is not None and strategy.runs == 1  # still ran


async def test_cycle_is_error_contained() -> None:
    rt = make_runtime()

    async def boom(_rt, _ctx):
        raise RuntimeError("provider down")

    # Break one agent's job; the rest of the pipeline must still complete.
    rt._agents["Research Agent"].job = boom  # type: ignore[assignment]
    await rt.run_cycle()
    research = rt.agent_runtime("Research Agent")
    assert research is not None and research.last_ok is False
    assert research.runtime_state == "error"
    # A later agent still produced a good tick.
    doc = rt.agent_runtime("Documentation Agent")
    assert doc is not None and doc.last_ok is True


async def test_control_unknown_agent() -> None:
    rt = make_runtime()
    accepted, reason, state = rt.control("Ghost Agent", "start")
    assert accepted is False and state == "unknown"
    assert "unknown" in reason.lower()
