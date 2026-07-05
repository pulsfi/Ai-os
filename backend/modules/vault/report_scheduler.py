"""Daily-report scheduler — the system writes its own diary.

One asyncio task: sleep until the configured UTC hour, append the fleet
report to today's daily note, repeat. Uses the same constrained write
path as the manual endpoint (path computed from the date, append-only).
Errors cost one day's entry, never the loop.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from modules.bots.manager import BotManager
from modules.vault.daily_report import build_daily_report
from modules.vault.vault_service import VaultService

logger = logging.getLogger(__name__)


def seconds_until_hour_utc(hour: int, now: datetime | None = None) -> float:
    """Seconds from `now` until the next occurrence of hour:00 UTC."""
    now = now or datetime.now(timezone.utc)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


class DailyReportScheduler:
    """Writes the fleet report into the daily note once per day."""

    def __init__(self, bots: BotManager, vault: VaultService, hour_utc: int) -> None:
        self._bots = bots
        self._vault = vault
        self._hour = hour_utc
        self._task: asyncio.Task[None] | None = None
        self.runs = 0

    def write_now(self) -> str:
        """One report write (used by the loop; callable from tests)."""
        section = build_daily_report(self._bots.statuses(), self._bots.performance())
        path = self._vault.append_daily_report(section)
        self.runs += 1
        return path

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(seconds_until_hour_utc(self._hour))
            try:
                path = self.write_now()
                logger.info("daily report auto-written to %s", path)
            except Exception:  # noqa: BLE001 — one bad day must not stop the diary
                logger.exception("daily report write failed; retrying tomorrow")

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="daily-report")
            logger.info("daily report scheduler started (%02d:00 UTC)", self._hour)

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
