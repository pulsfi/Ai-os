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
from models.schemas.bots import BotConfig, BotControlResult, BotStatus, BotTrade
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
