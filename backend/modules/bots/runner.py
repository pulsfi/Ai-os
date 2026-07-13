"""BotRunner — one live asyncio loop per bot.

Tick = (1) mark open positions to market and close any that hit
take-profit, stop-loss, or max-hold; (2) if slots are free, ask the
strategy for entries and open them. Every tick is error-contained: a
failing provider costs one tick, never the loop.

PAPER MODE ONLY — "open/close" means ledger rows with virtual USD.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from models.schemas.bots import BotConfig, BotState, BotStatus
from modules.bots.ledger import BotLedger
from modules.bots.profit_capture import (
    CaptureState,
    ProfitCaptureConfig,
    ProfitTier,
    evaluate as capture_evaluate,
)
from modules.bots.strategies import Strategy

logger = logging.getLogger(__name__)


class BotRunner:
    """Owns one bot's loop, state, and position bookkeeping."""

    def __init__(
        self,
        config: BotConfig,
        strategy: Strategy,
        ledger: BotLedger,
        exit_slippage_bps: int | None = None,
        max_gain_pct: float | None = None,
    ) -> None:
        self.config = config
        self._strategy = strategy
        self._ledger = ledger
        # Explicit args win (tests); otherwise use the bot's own config so
        # slippage/cap are per-bot and tunable at runtime.
        self._slippage_override = exit_slippage_bps
        self._gain_override = max_gain_pct
        self._task: asyncio.Task[None] | None = None
        self._state = BotState.STOPPED
        self._started_at: str | None = None
        self._ticks = 0
        self._errors = 0
        self._last_error: str | None = None
        # trade_id -> last seen price; lets max-hold close honestly when
        # live data for a dead launch disappears.
        self._last_price: dict[int, float] = {}
        # trade_id -> peak price since entry (drives the trailing stop).
        self._peak_price: dict[int, float] = {}
        # trade_id -> (capture state, original usd) for Dynamic Profit
        # Capture. In-memory like the peak marks: after a restart the open
        # remainder is treated as a fresh original (documented behaviour).
        self._capture: dict[int, tuple[CaptureState, float]] = {}
        # mint -> monotonic time until which re-entry is blocked (stops the
        # bot from re-buying the same coin over and over after each exit).
        self._cooldown: dict[str, float] = {}
        # One-shot: mints AND names this bot has EVER traded (never re-enter).
        # Blocking the name too stops copycat relaunches (same "ANIF" name,
        # fresh mint). Seeded from the ledger so a restart doesn't forget.
        self._seen_mints: set[str] = set()
        self._seen_symbols: set[str] = set()
        if config.one_shot_per_mint:
            self._seen_mints = ledger.traded_mints(config.id)
            self._seen_symbols = ledger.traded_symbols(config.id)
        # Risk governor: a bleeding recent record trades SMALLER, never stops.
        self._risk_note: str | None = None
        # Serializes scheduled ticks with event-driven request_tick calls.
        self._tick_lock = asyncio.Lock()

    # -- risk management -------------------------------------------------------

    GUARD_WINDOW = 20  # trades examined
    GUARD_MIN_TRADES = 12  # don't judge tiny samples
    GUARD_MIN_PF = 0.75  # profit factor below this = negative expectancy
    GUARD_SIZE_FACTOR = 0.5  # trade at half size while the record is bleeding

    def _risk_governor(self) -> float:
        """NEVER pauses trading: if the last GUARD_WINDOW closed trades have
        a profit factor under GUARD_MIN_PF, positions are HALVED until the
        rolling record recovers. Poor performance costs size, not uptime —
        the bot keeps trading (and keeps generating the evidence needed to
        judge the strategy) at reduced risk."""
        closed = [
            t for t in self._ledger.trades(self.config.id, limit=self.GUARD_WINDOW)
            if t.status == "closed"
        ]
        if len(closed) < self.GUARD_MIN_TRADES:
            self._risk_note = None
            return 1.0
        gains = sum(t.pnl_usd or 0.0 for t in closed if (t.pnl_usd or 0.0) > 0)
        losses = abs(sum(t.pnl_usd or 0.0 for t in closed if (t.pnl_usd or 0.0) < 0))
        pf = (gains / losses) if losses > 0 else float("inf")
        if pf < self.GUARD_MIN_PF:
            note = (
                f"risk-reduced: profit factor {pf:.2f} over the last {len(closed)} "
                f"trades — trading at half size until the record recovers"
            )
            if note != self._risk_note:
                logger.warning("bot %s %s", self.config.id, note)
            self._risk_note = note
            return self.GUARD_SIZE_FACTOR
        self._risk_note = None
        return 1.0

    def _position_size(self, confidence: float | None, governor: float = 1.0) -> float:
        """Adaptive sizing: conviction scales a position up (0.6x at the
        55 gate -> 1.2x at score 100); a cold recent streak scales it down;
        the risk governor halves it while the record is bleeding. Bounded —
        no single trade can balloon."""
        base = self.config.usd_per_trade
        scale = 1.0
        if confidence is not None:
            edge = max(0.0, min(confidence - 55.0, 45.0)) / 45.0
            scale = 0.6 + edge * 0.6
        recent = [
            t.pnl_usd or 0.0
            for t in self._ledger.trades(self.config.id, limit=10)
            if t.status == "closed"
        ]
        if len(recent) >= 5 and sum(recent) < 0:
            scale *= 0.7  # trade smaller while cold
        return round(base * scale * governor, 2)

    # -- control -------------------------------------------------------------

    def start(self) -> bool:
        """Begin the loop; False if already running."""
        if self._task is not None and not self._task.done():
            return False
        self._state = BotState.RUNNING
        self._started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._task = asyncio.create_task(self._run(), name=f"bot:{self.config.id}")
        logger.info("bot %s started (every %.0fs)", self.config.id, self.config.interval_s)
        return True

    async def stop(self) -> bool:
        """Cancel the loop; False if it was not running."""
        if self._task is None or self._task.done():
            self._state = BotState.STOPPED
            return False
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._state = BotState.STOPPED
        logger.info("bot %s stopped", self.config.id)
        return True

    # -- loop ------------------------------------------------------------------

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — a tick must never kill the loop
                self._errors += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("bot %s tick failed: %s", self.config.id, self._last_error)
            await asyncio.sleep(self.config.interval_s)

    async def tick(self) -> None:
        """One full evaluate cycle (public so tests can drive it directly)."""
        async with self._tick_lock:
            self._ticks += 1
            await self._manage_open_positions()
            await self._open_new_positions()

    def reset_marks(self) -> None:
        """Drop in-memory price marks (used after a ledger reset)."""
        self._last_price.clear()
        self._peak_price.clear()
        self._capture.clear()

    def request_tick(self) -> None:
        """Event-driven tick: evaluate NOW instead of waiting the interval.

        Called by the launch stream the instant a new token appears. The
        lock serializes it with the scheduled loop, so a burst of events
        can never double-enter a position.
        """
        if not self.is_running:
            return
        asyncio.create_task(self._event_tick(), name=f"bot:{self.config.id}:event")

    async def _event_tick(self) -> None:
        try:
            await self.tick()
        except Exception as exc:  # noqa: BLE001 — same containment as the loop
            self._errors += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "bot %s event tick failed: %s", self.config.id, self._last_error
            )

    async def _manage_open_positions(self) -> None:
        now = datetime.now(timezone.utc)
        for trade in self._ledger.open_trades(self.config.id):
            price = await self._strategy.current_price(trade.mint)
            if price is not None:
                self._last_price[trade.id] = price

            held_s = (now - datetime.fromisoformat(trade.entry_ts)).total_seconds()
            if price is not None:
                peak = max(self._peak_price.get(trade.id, trade.entry_price), price)
                self._peak_price[trade.id] = peak
                change_pct = (price - trade.entry_price) / trade.entry_price * 100
                peak_gain_pct = (peak - trade.entry_price) / trade.entry_price * 100
                if self.config.profit_capture.enabled:
                    # Dynamic Profit Capture owns the PROFIT side. The risk
                    # floor stays immediate: stop-loss and stall exit first,
                    # then tiered scale-out / tightening trail / time decay.
                    if change_pct <= -self.config.stop_loss_pct:
                        self._close(trade.id, trade.mint, trade.entry_price, price, "stop-loss")
                        continue
                    if (
                        self.config.stall_exit_s is not None
                        and held_s >= self.config.stall_exit_s
                        and peak_gain_pct < self.config.stall_min_gain_pct
                        and change_pct < self.config.stall_min_gain_pct
                    ):
                        self._close(
                            trade.id, trade.mint, trade.entry_price, price,
                            f"stall-exit (no move in {int(held_s)}s)",
                        )
                        continue
                    if self._capture_tick(trade, price, peak, held_s):
                        continue  # position fully closed by the engine
                    # fall through only to the bottom max-hold safety net
                elif change_pct >= self.config.take_profit_pct:
                    self._close(trade.id, trade.mint, trade.entry_price, price, "take-profit")
                    continue
                # Trailing stop: armed once the peak gain clears the
                # threshold; fires when price gives back too much of it.
                elif (
                    self.config.trail_after_pct is not None
                    and self.config.trail_drop_pct is not None
                    and peak_gain_pct >= self.config.trail_after_pct
                    and price <= peak * (1 - self.config.trail_drop_pct / 100)
                ):
                    self._close(
                        trade.id, trade.mint, trade.entry_price, price,
                        f"trailing-stop (peak +{peak_gain_pct:.1f}%)",
                    )
                    continue
                # Break-even stop: once a position has been meaningfully up,
                # never let it become a full stop-loss — exit ~flat instead
                # of round-tripping a winner into a -18% loser.
                elif (
                    self.config.break_even_at_pct is not None
                    and peak_gain_pct >= self.config.break_even_at_pct
                    and change_pct <= 0.5
                ):
                    self._close(
                        trade.id, trade.mint, trade.entry_price, price,
                        f"break-even stop (peak +{peak_gain_pct:.1f}%)",
                    )
                    continue
                # Stall exit (time stop): the impulse never came — get out
                # near flat instead of bleeding down to the full stop-loss.
                elif (
                    self.config.stall_exit_s is not None
                    and held_s >= self.config.stall_exit_s
                    and peak_gain_pct < self.config.stall_min_gain_pct
                    and change_pct < self.config.stall_min_gain_pct
                ):
                    self._close(
                        trade.id, trade.mint, trade.entry_price, price,
                        f"stall-exit (no move in {int(held_s)}s)",
                    )
                    continue
                elif change_pct <= -self.config.stop_loss_pct:
                    self._close(trade.id, trade.mint, trade.entry_price, price, "stop-loss")
                    continue
            if held_s >= self.config.max_hold_s:
                # Close at the last real price we saw; entry price if the
                # market data vanished before the first mark (honest note).
                exit_price = self._last_price.get(trade.id, trade.entry_price)
                note = f"max-hold {int(held_s)}s"
                if trade.id not in self._last_price:
                    note += " (no live price seen; closed flat)"
                self._close(trade.id, trade.mint, trade.entry_price, exit_price, note)

    def _capture_cfg(self) -> ProfitCaptureConfig:
        """Bridge the persisted per-bot settings into the pure engine's
        config. max_hold_s stays single-sourced from the bot config."""
        pc = self.config.profit_capture
        return ProfitCaptureConfig(
            enabled=pc.enabled,
            tiers=[ProfitTier(t.gain_pct, t.sell_pct) for t in pc.tiers],
            base_trail_drop_pct=pc.base_trail_drop_pct,
            min_trail_drop_pct=pc.min_trail_drop_pct,
            decay_after_s=pc.decay_after_s,
            max_hold_s=self.config.max_hold_s,
        )

    def _capture_tick(self, trade, price: float, peak: float, held_s: float) -> bool:
        """Run the Dynamic Profit Capture engine for one open position.
        Executes its actions through the same slippage-modelled fill path
        as every other exit. Returns True if the position fully closed."""
        state, original_usd = self._capture.get(trade.id) or (CaptureState(), trade.usd_size)
        self._capture[trade.id] = (state, original_usd)
        actions = capture_evaluate(
            entry_price=trade.entry_price, price=price, peak_price=peak,
            held_s=held_s, cfg=self._capture_cfg(), state=state,
        )
        for action in actions:
            if action.kind == "partial_sell":
                exit_price, suffix = self._realistic_exit(trade.entry_price, price)
                slice_usd = min(round(original_usd * action.sell_frac, 4), trade.usd_size)
                slice_id = self._ledger.partial_close(
                    trade.id, slice_usd, exit_price,
                    f"profit-capture {action.reason}{suffix}",
                )
                if slice_id is not None:
                    state.remaining_frac = max(0.0, state.remaining_frac - action.sell_frac)
                    logger.info(
                        "bot %s profit-capture %s on %s: slice $%.2f realized",
                        self.config.id, action.reason, trade.symbol, slice_usd,
                    )
            else:  # full_close
                self._close(
                    trade.id, trade.mint, trade.entry_price, price,
                    f"profit-capture {action.reason}",
                )
                return True
        return False

    def _realistic_exit(self, entry_price: float, mark: float) -> tuple[float, str]:
        """Model a realizable fill: a slippage haircut on every exit, and a
        per-trade gain cap (you can't dump a fresh illiquid launch at an
        overshot mark). Slippage/cap are per-bot. Returns (exit_price, note)."""
        slippage = (
            self._slippage_override
            if self._slippage_override is not None
            else self.config.exit_slippage_bps
        )
        max_gain = (
            self._gain_override
            if self._gain_override is not None
            else self.config.max_gain_pct
        )
        exit_price = mark * (1 - slippage / 10_000)
        suffix = ""
        cap_price = entry_price * (1 + max_gain / 100)
        if exit_price > cap_price:
            exit_price = cap_price
            suffix = f" · capped +{max_gain:.0f}%"
        return exit_price, suffix

    def _close(
        self, trade_id: int, mint: str, entry_price: float, mark: float, note: str
    ) -> None:
        exit_price, suffix = self._realistic_exit(entry_price, mark)
        realized_pct = (exit_price - entry_price) / entry_price * 100 if entry_price else 0.0
        self._ledger.close_trade(
            trade_id, exit_price, f"{note} {realized_pct:+.1f}%{suffix}"
        )
        self._last_price.pop(trade_id, None)
        self._peak_price.pop(trade_id, None)
        self._capture.pop(trade_id, None)
        # Block re-buying this same coin until the cooldown expires.
        self._cooldown[mint] = time.monotonic() + self.config.reentry_cooldown_s
        # Let the strategy release live-stream resources for this mint.
        asyncio.create_task(self._strategy.on_position_closed(mint))
        logger.info("bot %s closed trade %s: %s %+.1f%%", self.config.id, trade_id, note, realized_pct)

    async def _open_new_positions(self) -> None:
        open_trades = self._ledger.open_trades(self.config.id)
        slots = self.config.max_open_positions - len(open_trades)
        if slots <= 0:
            return
        # A bleeding recent record halves size — it never halts entries.
        governor = self._risk_governor()
        # Exclude held mints, mints in cooldown, and (one-shot) any mint
        # ever traded — one chance per coin, then on to the next.
        now = time.monotonic()
        self._cooldown = {m: exp for m, exp in self._cooldown.items() if exp > now}
        blocked = {t.mint for t in open_trades} | set(self._cooldown) | self._seen_mints
        held_symbols = {t.symbol.strip().lower() for t in open_trades}
        for signal in await self._strategy.find_entries(blocked, slots):
            sym = signal.symbol.strip().lower()
            # Skip names already traded (copycat relaunch) or held right now —
            # logged, never silent: an approved signal that doesn't become an
            # order must always say why.
            if self.config.one_shot_per_mint and sym in self._seen_symbols:
                logger.info(
                    "bot %s skipped approved %s: symbol already traded (one-shot)",
                    self.config.id, signal.symbol,
                )
                continue
            if sym and sym in held_symbols:
                logger.info(
                    "bot %s skipped approved %s: same symbol held right now",
                    self.config.id, signal.symbol,
                )
                continue
            trade_id = self._ledger.open_trade(
                bot_id=self.config.id,
                mint=signal.mint,
                symbol=signal.symbol,
                usd_size=self._position_size(signal.confidence, governor),
                entry_price=signal.price_usd,
                entry_note=signal.note,
            )
            held_symbols.add(sym)
            if self.config.one_shot_per_mint:
                self._seen_mints.add(signal.mint)
                self._seen_symbols.add(sym)
            self._last_price[trade_id] = signal.price_usd
            self._peak_price[trade_id] = signal.price_usd
            logger.info(
                "bot %s opened %s (%s) @ %.10f — %s",
                self.config.id, signal.symbol, trade_id, signal.price_usd, signal.note,
            )

    # -- status ---------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> BotStatus:
        # A crashed task (should be impossible — ticks are contained) shows as error.
        if self._task is not None and self._task.done() and not self._task.cancelled():
            exc = self._task.exception()
            if exc is not None:
                self._state = BotState.ERROR
                self._last_error = f"{type(exc).__name__}: {exc}"
        stats = self._ledger.stats(self.config.id)
        return BotStatus(
            config=self.config,
            state=self._state if self.is_running or self._state == BotState.ERROR else BotState.STOPPED,
            started_at=self._started_at if self.is_running else None,
            ticks=self._ticks,
            errors=self._errors,
            last_error=self._last_error,
            risk_note=self._risk_note,
            **stats,  # type: ignore[arg-type]
        )
