"""Market scheduler — periodic asynchronous refresh of the watchlist.

A plain asyncio task (no extra dependency at this stage): started by the
app lifespan when MARKET_REFRESH_ENABLED=true, cancelled cleanly on
shutdown. Interval is configurable via MARKET_REFRESH_SECONDS.

TODO(market): move to a proper worker (arq) when jobs multiply — the
Phase 2 decision tracked in docs/ROADMAP.md.
"""

import asyncio
import logging

from modules.market.market_manager import MarketManager

logger = logging.getLogger(__name__)


class MarketScheduler:
    """Owns the background refresh loop for one MarketManager."""

    def __init__(self, manager: MarketManager, interval_s: int) -> None:
        self._manager = manager
        self._interval = max(30, interval_s)  # floor: never hammer providers
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Launch the loop; idempotent."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="market-refresh")
            logger.info("Market scheduler started (every %ss)", self._interval)

    async def stop(self) -> None:
        """Cancel the loop and wait for it to unwind."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("Market scheduler stopped")

    async def _run(self) -> None:
        """Refresh, sleep, repeat — one failure never kills the loop."""
        while True:
            try:
                await self._manager.refresh_all()
            except Exception as exc:  # noqa: BLE001 — the loop must survive
                logger.error("scheduled refresh failed: %s", exc)
            await asyncio.sleep(self._interval)
