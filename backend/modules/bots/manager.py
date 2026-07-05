"""BotManager — builds the fleet, controls it, reports on it.

The default fleet is three bots with deliberately different styles so
their paper track records can be compared:

    sniper    — new pump.fun launches (highest risk, fastest)
    graduate  — bonding-curve graduation momentum
    trend     — watchlist 24h movers (real merged prices; the baseline)

start/stop/restart here are REAL state changes on asyncio tasks — this is
the runtime the /agents endpoints were honestly missing.
"""

import logging
from pathlib import Path

from config import Settings
from core.exceptions import NotFoundError
from models.schemas.bots import (
    BotConfig,
    BotControlResult,
    BotPerformance,
    BotStatus,
    BotTrade,
    EquityPoint,
)
from modules.bots.ledger import BotLedger
from modules.bots.runner import BotRunner
from modules.bots.strategies import (
    GraduationMomentum,
    NewLaunchSniper,
    TrendScalper,
)
from modules.market import get_market_manager
from modules.market.pumpfun import get_pumpfun_client

logger = logging.getLogger(__name__)


def _default_configs(settings: Settings) -> list[BotConfig]:
    usd = settings.bots_usd_per_trade
    return [
        BotConfig(
            id="sniper",
            name="Launch Sniper",
            strategy="new_launch_sniper",
            description="Buys brand-new pump.fun launches with early traction",
            interval_s=settings.bots_interval_seconds,
            usd_per_trade=usd,
            max_open_positions=3,
            take_profit_pct=40.0,
            stop_loss_pct=25.0,
            max_hold_s=15 * 60,
        ),
        BotConfig(
            id="graduate",
            name="Graduation Rider",
            strategy="graduation_momentum",
            description="Rides pump.fun coins through bonding-curve graduation",
            interval_s=settings.bots_interval_seconds,
            usd_per_trade=usd,
            max_open_positions=3,
            take_profit_pct=20.0,
            stop_loss_pct=12.0,
            max_hold_s=60 * 60,
        ),
        BotConfig(
            id="trend",
            name="Trend Scalper",
            strategy="trend_scalper",
            description="Scalps the watchlist's strongest 24h movers (baseline bot)",
            interval_s=max(settings.bots_interval_seconds, 30.0),
            usd_per_trade=usd,
            max_open_positions=2,
            take_profit_pct=3.0,
            stop_loss_pct=2.0,
            max_hold_s=6 * 60 * 60,
        ),
    ]


class BotManager:
    """Owns the ledger and every runner; the only fleet entry point."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ledger = BotLedger(Path(settings.bots_db_path))
        pumpfun = get_pumpfun_client(settings)
        market = get_market_manager(settings)
        strategies = {
            "new_launch_sniper": NewLaunchSniper(pumpfun, market),
            "graduation_momentum": GraduationMomentum(pumpfun, market),
            "trend_scalper": TrendScalper(pumpfun, market),
        }
        self._runners: dict[str, BotRunner] = {}
        for config in _default_configs(settings):
            self._runners[config.id] = BotRunner(
                config, strategies[config.strategy], self._ledger
            )
        logger.info("Bot fleet built: %s (PAPER MODE)", ", ".join(self._runners))

    # -- fleet control -----------------------------------------------------

    def start_all(self) -> None:
        for runner in self._runners.values():
            runner.start()

    async def stop_all(self) -> None:
        for runner in self._runners.values():
            await runner.stop()

    def _runner(self, bot_id: str) -> BotRunner:
        runner = self._runners.get(bot_id)
        if runner is None:
            raise NotFoundError(f"Unknown bot: {bot_id}")
        return runner

    async def control(self, bot_id: str, action: str) -> BotControlResult:
        """start | stop | restart — real task lifecycle, honest result."""
        runner = self._runner(bot_id)
        if action == "start":
            changed = runner.start()
            detail = "Bot loop started." if changed else "Bot was already running."
        elif action == "stop":
            changed = await runner.stop()
            detail = "Bot loop stopped." if changed else "Bot was not running."
        else:  # restart (action validated at the router)
            await runner.stop()
            runner.start()
            changed = True
            detail = "Bot loop restarted."
        return BotControlResult(
            bot_id=bot_id,
            action=action,
            accepted=changed,
            state=runner.status().state,
            detail=f"{detail} Paper mode: virtual USD only.",
        )

    # -- reporting ------------------------------------------------------------

    def statuses(self) -> list[BotStatus]:
        return [r.status() for r in self._runners.values()]

    def trades(self, bot_id: str | None = None, limit: int = 50) -> list[BotTrade]:
        if bot_id is not None:
            self._runner(bot_id)  # 404 for unknown bots
        return self._ledger.trades(bot_id, limit)

    def performance(self) -> list[BotPerformance]:
        """Track record per bot, plus the whole fleet as id 'fleet'.

        The curve is cumulative REALIZED PnL — only closed trades move it,
        so it never flatters the fleet with unrealized paper gains.
        """
        results: list[BotPerformance] = []
        specs = [("fleet", "Whole fleet", None)] + [
            (r.config.id, r.config.name, r.config.id) for r in self._runners.values()
        ]
        for perf_id, name, ledger_id in specs:
            closed = self._ledger.closed_trades_chrono(ledger_id)
            equity = 0.0
            curve: list[EquityPoint] = []
            pcts: list[float] = []
            wins = 0
            for t in closed:
                equity += t.pnl_usd or 0.0
                curve.append(
                    EquityPoint(ts=t.exit_ts or t.entry_ts, equity_usd=round(equity, 4))
                )
                if t.pnl_pct is not None:
                    pcts.append(t.pnl_pct)
                if (t.pnl_usd or 0.0) > 0:
                    wins += 1
            n = len(closed)
            results.append(
                BotPerformance(
                    bot_id=perf_id,
                    name=name,
                    closed_trades=n,
                    wins=wins,
                    losses=n - wins,
                    win_rate_pct=round(wins / n * 100, 1) if n else None,
                    realized_pnl_usd=round(equity, 2),
                    avg_pnl_pct=round(sum(pcts) / len(pcts), 2) if pcts else None,
                    best_trade_pct=max(pcts) if pcts else None,
                    worst_trade_pct=min(pcts) if pcts else None,
                    curve=curve,
                )
            )
        return results


_manager: BotManager | None = None


def get_bot_manager(settings: Settings) -> BotManager:
    """Process-wide singleton, same pattern as the other modules."""
    global _manager
    if _manager is None:
        _manager = BotManager(settings)
    return _manager


async def close_bot_manager() -> None:
    """Stop every bot loop (app shutdown)."""
    global _manager
    if _manager is not None:
        await _manager.stop_all()
        _manager = None
