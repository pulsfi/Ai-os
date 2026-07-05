"""PumpPortal launch stream — real-time pump.fun events over WebSocket.

This is the fast path for meme sniping: instead of polling REST every N
seconds, PumpPortal (a free community data relay, wss://pumpportal.fun)
pushes every new token creation and — for mints we watch — every trade,
the moment they hit the chain. Detection latency drops from "up to one
tick interval" to "as soon as the event arrives".

READ-ONLY: this socket receives data. It never sends transactions,
never holds keys. Reconnects with capped backoff; while disconnected
the sniper's REST polling keeps working, so the stream is a speed
upgrade, never a single point of failure.
"""

import asyncio
import contextlib
import json
import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

import websockets

from config import Settings

logger = logging.getLogger(__name__)

_URL = "wss://pumpportal.fun/api/data"


@dataclass(frozen=True)
class LaunchEvent:
    """One new pump.fun token creation, as received from the stream."""

    mint: str
    name: str
    symbol: str
    mcap_sol: float | None
    received_at: float = field(default_factory=time.monotonic)


class LaunchStream:
    """Maintains the live event feed + latest trade marks for watched mints."""

    def __init__(self) -> None:
        self._events: deque[LaunchEvent] = deque(maxlen=300)
        self._trade_mcap: dict[str, tuple[float, float]] = {}  # mint -> (mcapSol, mono)
        self._watched: set[str] = set()
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task[None] | None = None
        self._ws: websockets.ClientConnection | None = None
        self.connected = False
        self.events_seen = 0
        self.trades_seen = 0

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="launch-stream")
            logger.info("launch stream starting (%s)", _URL)

    async def aclose(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        self.connected = False

    async def _run(self) -> None:
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(_URL, ping_interval=30) as ws:
                    self._ws = ws
                    self.connected = True
                    backoff = 1.0
                    logger.info("launch stream connected")
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    if self._watched:  # resubscribe after reconnects
                        await ws.send(
                            json.dumps(
                                {"method": "subscribeTokenTrade", "keys": sorted(self._watched)}
                            )
                        )
                    async for raw in ws:
                        self._handle(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — any disconnect -> retry
                logger.warning(
                    "launch stream dropped (%s: %s); retry in %.0fs",
                    type(exc).__name__, exc, backoff,
                )
            self._ws = None
            self.connected = False
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    def _handle(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(msg, dict):
            return
        tx_type = msg.get("txType")
        mint = msg.get("mint")
        if tx_type == "create" and isinstance(mint, str):
            self.events_seen += 1
            mcap = msg.get("marketCapSol")
            self._events.append(
                LaunchEvent(
                    mint=mint,
                    name=str(msg.get("name") or ""),
                    symbol=str(msg.get("symbol") or ""),
                    mcap_sol=float(mcap) if isinstance(mcap, (int, float)) else None,
                )
            )
            for listener in self._listeners:
                try:
                    listener()
                except Exception:  # noqa: BLE001 — a listener must not kill the feed
                    logger.exception("launch stream listener failed")
        elif tx_type in ("buy", "sell") and isinstance(mint, str):
            mcap = msg.get("marketCapSol")
            if isinstance(mcap, (int, float)):
                self.trades_seen += 1
                self._trade_mcap[mint] = (float(mcap), time.monotonic())

    # -- consumption -----------------------------------------------------------

    def add_listener(self, listener: Callable[[], None]) -> None:
        """Called synchronously on every new launch (keep it tiny)."""
        self._listeners.append(listener)

    def recent(self, max_age_s: float) -> list[LaunchEvent]:
        """Fresh launches, newest first."""
        cutoff = time.monotonic() - max_age_s
        return [e for e in reversed(self._events) if e.received_at >= cutoff]

    def latest_mcap_sol(self, mint: str, max_age_s: float = 20.0) -> float | None:
        """The mint's market cap (SOL) from its most recent streamed trade."""
        entry = self._trade_mcap.get(mint)
        if entry is None or time.monotonic() - entry[1] > max_age_s:
            return None
        return entry[0]

    async def watch(self, mint: str) -> None:
        """Stream this mint's trades (live price marks for an open position)."""
        if mint in self._watched:
            return
        self._watched.add(mint)
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.send(
                    json.dumps({"method": "subscribeTokenTrade", "keys": [mint]})
                )

    async def unwatch(self, mint: str) -> None:
        self._watched.discard(mint)
        self._trade_mcap.pop(mint, None)
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.send(
                    json.dumps({"method": "unsubscribeTokenTrade", "keys": [mint]})
                )

    def stats(self) -> dict[str, int | bool]:
        return {
            "connected": self.connected,
            "events_seen": self.events_seen,
            "trades_seen": self.trades_seen,
            "watched": len(self._watched),
        }


_stream: LaunchStream | None = None


def get_launch_stream(_settings: Settings) -> LaunchStream:
    """Process-wide singleton (started explicitly by the bot manager)."""
    global _stream
    if _stream is None:
        _stream = LaunchStream()
    return _stream


async def close_launch_stream() -> None:
    global _stream
    if _stream is not None:
        await _stream.aclose()
        _stream = None
