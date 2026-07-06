"""BotRunner — one live asyncio loop per bot.

Tick = (1) mark open positions to market and close any that hit
take-profit, stop-loss, or max-hold; (2) if slots are free, ask the
strategy for entries and open them. Every tick is error-contained: a
failing provider costs one tick, never the loop.

PAPER MODE ONLY — "open/close" means ledger rows with virtual USD.
"""

import asyncio
import logging
from datetime import datetime, timezone

from models.schemas.bots import BotConfig, BotState, BotStatus
from modules.bots.ledger import BotLedger
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
        # Serializes scheduled ticks with event-driven request_tick calls.
        self._tick_lock = asyncio.Lock()

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
                if change_pct >= self.config.take_profit_pct:
                    self._close(trade.id, trade.mint, trade.entry_price, price, "take-profit")
                    continue
                # Trailing stop: armed once the peak gain clears the
                # threshold; fires when price gives back too much of it.
                if (
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
                if change_pct <= -self.config.stop_loss_pct:
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
        # Let the strategy release live-stream resources for this mint.
        asyncio.create_task(self._strategy.on_position_closed(mint))
        logger.info("bot %s closed trade %s: %s %+.1f%%", self.config.id, trade_id, note, realized_pct)

    async def _open_new_positions(self) -> None:
        open_trades = self._ledger.open_trades(self.config.id)
        slots = self.config.max_open_positions - len(open_trades)
        if slots <= 0:
            return
        held = {t.mint for t in open_trades}
        for signal in await self._strategy.find_entries(held, slots):
            trade_id = self._ledger.open_trade(
                bot_id=self.config.id,
                mint=signal.mint,
                symbol=signal.symbol,
                usd_size=self.config.usd_per_trade,
                entry_price=signal.price_usd,
                entry_note=signal.note,
            )
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
            **stats,  # type: ignore[arg-type]
        )
