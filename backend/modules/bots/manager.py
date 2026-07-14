"""BotManager — builds the fleet, controls it, reports on it.

The default fleet is three bots with deliberately different styles so
their paper track records can be compared:

    sniper    — new pump.fun launches (highest risk, fastest)
    graduate  — bonding-curve graduation momentum
    trend     — watchlist 24h movers (real merged prices; the baseline)

start/stop/restart here are REAL state changes on asyncio tasks — this is
the runtime the /agents endpoints were honestly missing.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from core.exceptions import NotFoundError

from models.schemas.bots import (
    BotConfig,
    BotConfigUpdate,
    BotControlResult,
    BotInsights,
    BotPerformance,
    BotStatus,
    BotTrade,
    EquityPoint,
    FactorInsight,
    ProfitCaptureSettings,
    SniperTelemetry,
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
                "Scores every pump.fun launch 0-100 on native signals "
                "(authority rug/honeypot gates, market-cap velocity, bonding "
                "progress, community, age). CONFIRMATION entry: never buys on "
                "first sight — only once it has watched the cap actually climb"
            ),
            interval_s=settings.bots_sniper_interval_seconds,
            usd_per_trade=usd,
            max_open_positions=3,
            take_profit_pct=40.0,
            stop_loss_pct=18.0,  # tighter: cut losers faster (was 25%)
            max_hold_s=15 * 60,
            trail_after_pct=15.0,  # up 15%? protect it:
            trail_drop_pct=8.0,  # give back 8% from peak -> out (let winners run less far back)
            break_even_at_pct=10.0,  # once +10%, never let it become a -18% loss
            stall_exit_s=90.0,  # no move in 90s = failed impulse -> out ~flat
            stall_min_gain_pct=3.0,
            # Dynamic Profit Capture: tiered scale-out with a tightening
            # trail replaces the fixed +40% take-profit on the sniper.
            profit_capture=ProfitCaptureSettings(enabled=True),
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
            break_even_at_pct=6.0,
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
        from modules.backtest.recorder import get_recorder

        strategies = {
            "new_launch_sniper": NewLaunchSniper(
                pumpfun, market, helius, stream=self._stream,
                rpc=get_rpc_client(settings),
                recorder=get_recorder(settings),
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
            strategy = strategies[config.strategy]
            # The execution threshold lives on the config (tunable,
            # persisted) — push it into scoring strategies at build time.
            if hasattr(strategy, "_min_confidence"):
                strategy._min_confidence = config.min_confidence
            self._runners[config.id] = BotRunner(config, strategy, self._ledger)
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
            # Execution threshold applies LIVE — the strategy gates on it.
            if "min_confidence" in changes and hasattr(runner._strategy, "_min_confidence"):
                runner._strategy._min_confidence = changes["min_confidence"]
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
        today = datetime.now(timezone.utc).date().isoformat()
        for perf_id, name, ledger_id in specs:
            closed = self._ledger.closed_trades_chrono(ledger_id)
            equity = 0.0
            peak = 0.0
            max_dd = 0.0
            gross_win = gross_loss = 0.0
            today_pnl = 0.0
            curve: list[EquityPoint] = []
            pcts: list[float] = []
            win_pcts: list[float] = []
            loss_pcts: list[float] = []
            wins = 0
            for t in closed:
                pnl = t.pnl_usd or 0.0
                equity += pnl
                peak = max(peak, equity)
                max_dd = max(max_dd, peak - equity)
                if pnl > 0:
                    wins += 1
                    gross_win += pnl
                else:
                    gross_loss += -pnl
                if (t.exit_ts or "").startswith(today):
                    today_pnl += pnl
                curve.append(
                    EquityPoint(ts=t.exit_ts or t.entry_ts, equity_usd=round(equity, 4))
                )
                if t.pnl_pct is not None:
                    pcts.append(t.pnl_pct)
                    (win_pcts if t.pnl_pct > 0 else loss_pcts).append(t.pnl_pct)
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
                    # Undefined with no losses yet (infinite) — shown as None.
                    profit_factor=round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
                    expectancy_usd=round(equity / n, 2) if n else None,
                    avg_win_pct=round(sum(win_pcts) / len(win_pcts), 2) if win_pcts else None,
                    avg_loss_pct=round(sum(loss_pcts) / len(loss_pcts), 2) if loss_pcts else None,
                    max_drawdown_usd=round(max_dd, 2) if n else None,
                    today_pnl_usd=round(today_pnl, 2),
                    curve=curve,
                )
            )
        return results

    def sniper_telemetry(self) -> SniperTelemetry:
        """The sniper's signals funnel: seen / rejected (+why) / executed."""
        runner = self._runners.get("sniper")
        strat = runner._strategy if runner is not None else None
        data = strat.telemetry() if hasattr(strat, "telemetry") else {}
        stats = self._ledger.stats("sniper")
        executed = int(stats["open_positions"] or 0) + int(stats["closed_trades"] or 0)
        return SniperTelemetry(trades_executed=executed, **data)

    _FACTOR_RE = re.compile(r"([a-z_]+) ([0-9.]+)/([0-9.]+)")

    def insights(self, bot_id: str = "sniper", limit: int = 400) -> BotInsights:
        """Factor-level win/loss analysis parsed from real trade notes.

        Shows which scoring factors actually separated winners from losers —
        the evidence base for reviewing weights. Deliberately NOT applied
        automatically: silently self-tuning weights on a small live sample
        overfits noise and hides the decision from the operator."""
        closed = [
            t for t in self._ledger.trades(bot_id, limit)
            if t.status == "closed" and t.entry_note and "[" in t.entry_note
        ]
        buckets: dict[str, dict[str, list[float]]] = {}
        wins = losses = 0
        for t in closed:
            won = (t.pnl_usd or 0.0) > 0
            wins += won
            losses += not won
            section = t.entry_note[t.entry_note.index("[") + 1:]
            for name, pts, _mx in self._FACTOR_RE.findall(section):
                buckets.setdefault(name, {"w": [], "l": []})["w" if won else "l"].append(
                    float(pts)
                )
        factors = []
        for name, b in sorted(buckets.items()):
            w_avg = round(sum(b["w"]) / len(b["w"]), 1) if b["w"] else None
            l_avg = round(sum(b["l"]) / len(b["l"]), 1) if b["l"] else None
            factors.append(FactorInsight(
                name=name, winners_avg=w_avg, losers_avg=l_avg,
                edge=round(w_avg - l_avg, 1) if w_avg is not None and l_avg is not None else None,
            ))
        return BotInsights(
            bot_id=bot_id, closed_analyzed=len(closed), wins=wins, losses=losses,
            factors=factors,
            note=(
                "Positive edge = the factor scored higher on winners. Small-sample "
                "correlation: use to review weights manually, not to auto-tune."
            ),
        )


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
