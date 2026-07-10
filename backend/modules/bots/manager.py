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
import json

from models.schemas.bots import (
    BotConfig,
    BotConfigUpdate,
    BotControlResult,
    BotPerformance,
    BotStatus,
    BotTrade,
    EquityPoint,
)
from modules.bots.ledger import BotLedger
from modules.bots.runner import BotRunner
from modules.bots.strategies import (
    FlowScalper,
    GraduationMomentum,
    NewLaunchSniper,
    TrendScalper,
)
from modules.market import get_market_manager
from modules.market.helius import get_helius_client
from modules.market.pumpfun import get_pumpfun_client
from modules.market.pumpportal import LaunchStream, get_launch_stream
from modules.solana import get_rpc_client

logger = logging.getLogger(__name__)


def _default_configs(settings: Settings) -> list[BotConfig]:
    usd = settings.bots_usd_per_trade
    return [
        BotConfig(
            id="sniper",
            name="Launch Sniper",
            strategy="new_launch_sniper",
            description=(
                "Scores every launch 0-100 on real signals (authority rug/"
                "honeypot gates, buy pressure, unique wallets, mcap, age) and "
                "only buys high-confidence ones — never blind"
            ),
            interval_s=settings.bots_sniper_interval_seconds,
            usd_per_trade=usd,
            max_open_positions=3,
            take_profit_pct=40.0,
            stop_loss_pct=18.0,  # tighter: cut losers faster (was 25%)
            max_hold_s=15 * 60,
            trail_after_pct=15.0,  # up 15%? protect it:
            trail_drop_pct=8.0,  # give back 8% from peak -> out (let winners run less far back)
            # Fresh launches are thin: a real exit is much worse than the
            # marked mcap. 3% haircut + a modest cap keeps paper honest —
            # you can't actually dump a new launch at +300%.
            exit_slippage_bps=300,
            max_gain_pct=60.0,
            reentry_cooldown_s=900.0,
            one_shot_per_mint=True,  # one snipe per launch — never chase it again
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
            trail_after_pct=8.0,
            trail_drop_pct=5.0,
            exit_slippage_bps=150,  # graduating coins: ~1.5% haircut
            max_gain_pct=100.0,
            reentry_cooldown_s=1800.0,
            one_shot_per_mint=True,  # a coin graduates once
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
            trail_after_pct=2.0,
            trail_drop_pct=1.0,
            # Watchlist tokens (SOL/JUP/BONK/WIF) are deeply liquid — real
            # slippage on a $50 order is tiny. The old 2% flat haircut is
            # what turned this bot's 3% wins into losses.
            exit_slippage_bps=25,  # 0.25%
            max_gain_pct=100000.0,  # no cap needed on liquid real prices
            reentry_cooldown_s=120.0,  # scalper can re-trade a liquid token sooner
        ),
        BotConfig(
            id="flowscalp",
            name="Flow Scalper",
            strategy="flow_scalper",
            description="Scalps liquid tokens only when live buy-pressure is "
            "confirmed (Helius flow) — disciplined, small quick wins",
            interval_s=max(settings.bots_interval_seconds, 25.0),
            usd_per_trade=usd,
            max_open_positions=2,
            take_profit_pct=2.5,
            stop_loss_pct=1.5,
            max_hold_s=2 * 60 * 60,
            trail_after_pct=1.5,
            trail_drop_pct=0.8,
            exit_slippage_bps=25,  # liquid, real fills
            max_gain_pct=100000.0,
            reentry_cooldown_s=90.0,
            one_shot_per_mint=False,  # liquid majors are re-tradeable
        ),
    ]


class BotManager:
    """Owns the ledger and every runner; the only fleet entry point."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ledger = BotLedger(Path(settings.bots_db_path))
        pumpfun = get_pumpfun_client(settings)
        market = get_market_manager(settings)
        helius = get_helius_client(settings)  # flow gate; inactive without a key
        # Real-time launch stream: event-driven entries + live trade marks.
        self._stream: LaunchStream | None = (
            get_launch_stream(settings) if settings.pumpportal_enabled else None
        )
        strategies = {
            "new_launch_sniper": NewLaunchSniper(
                pumpfun, market, helius, stream=self._stream,
                rpc=get_rpc_client(settings),
            ),
            "graduation_momentum": GraduationMomentum(pumpfun, market),
            "trend_scalper": TrendScalper(pumpfun, market),
            "flow_scalper": FlowScalper(pumpfun, market, helius),
        }
        self._overrides_path = Path(settings.bots_overrides_path)
        self._overrides = self._load_overrides()
        self._runners: dict[str, BotRunner] = {}
        for config in _default_configs(settings):
            # Apply any saved user tuning on top of the defaults.
            if self._overrides.get(config.id):
                config = config.model_copy(update=self._overrides[config.id])
            # slippage/cap now live on each BotConfig (per-bot, tunable).
            self._runners[config.id] = BotRunner(
                config, strategies[config.strategy], self._ledger
            )
        logger.info("Bot fleet built: %s (PAPER MODE)", ", ".join(self._runners))

    # -- config tuning ------------------------------------------------------

    def _load_overrides(self) -> dict[str, dict]:
        try:
            return json.loads(self._overrides_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _persist_overrides(self) -> None:
        try:
            self._overrides_path.parent.mkdir(parents=True, exist_ok=True)
            self._overrides_path.write_text(
                json.dumps(self._overrides, indent=2), encoding="utf-8"
            )
        except OSError as exc:  # persistence is best-effort
            logger.warning("could not persist bot overrides: %s", exc)

    def update_config(self, bot_id: str, update: BotConfigUpdate) -> BotStatus:
        """Apply a tuning change to a bot's config (paper only) and persist it."""
        runner = self._runner(bot_id)  # 404 for unknown bots
        changes = update.model_dump(exclude_none=True)
        if changes:
            runner.config = runner.config.model_copy(update=changes)
            self._overrides[bot_id] = {**self._overrides.get(bot_id, {}), **changes}
            self._persist_overrides()
            logger.info("bot %s config updated: %s", bot_id, changes)
        return runner.status()

    # -- fleet control -----------------------------------------------------

    def start_all(self) -> None:
        if self._stream is not None:
            self._stream.start()
            # New launch event -> the sniper evaluates immediately.
            self._stream.add_listener(self._runners["sniper"].request_tick)
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

    def first_entry_ts(self) -> str | None:
        """Earliest trade time across the fleet (drives days-of-record)."""
        return self._ledger.first_entry_ts()

    def reset_ledger(self) -> int:
        """Wipe the paper track record and per-bot marks (fresh start)."""
        n = self._ledger.reset()
        for runner in self._runners.values():
            runner.reset_marks()
        return n

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
