"""Provider adapters — one isolated interface per market data source.

Every provider implements `MarketProvider`; the rest of the module only
sees that interface, so providers can be added/swapped without touching
service code (Open/Closed + Dependency Inversion).

The base class centralizes the cross-cutting requirements:
- per-provider rate guard (never exceed provider limits)
- latency / error / availability statistics (monitoring)
- uniform logging of API and parsing failures
"""

import abc
import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

from modules.market.market_models import ProviderQuote, ProviderStatus

logger = logging.getLogger(__name__)


class MarketProvider(abc.ABC):
    """Base adapter: rate limiting, stats, and error containment."""

    name: str = "base"

    def __init__(self, http: httpx.AsyncClient, min_interval_s: float = 1.0) -> None:
        """
        Args:
            http: shared AsyncClient (owned by the manager, not the adapter).
            min_interval_s: minimum seconds between calls to this provider.
        """
        self._http = http
        self._min_interval = min_interval_s
        self._last_call = 0.0
        # monitoring counters
        self._calls = 0
        self._errors = 0
        self._latency_total_ms = 0.0
        self._last_success: datetime | None = None
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        """False when the provider needs a key it does not have."""
        return True

    async def get_quote(self, mint: str) -> ProviderQuote | None:
        """Fetch one token quote; never raises — failures return None.

        The wrapper enforces the rate guard, measures latency, and keeps
        the stats that /market/status exposes.
        """
        if not self.configured:
            return None
        # Rate guard DELAYS instead of dropping: a burst of tokens (watchlist
        # sweep) is spaced out to the provider's pace, never lost. Discovered
        # live: skip-behavior silently dropped 3 of 4 watchlist tokens.
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            logger.debug("rate-guard: delaying %s by %.2fs", self.name, wait)
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()
        self._calls += 1
        start = time.perf_counter()
        try:
            quote = await self._fetch(mint)
            self._latency_total_ms += (time.perf_counter() - start) * 1000
            self._last_success = datetime.now(timezone.utc)
            return quote
        except Exception as exc:  # noqa: BLE001 — adapters must not leak
            self._errors += 1
            self._last_error = f"{type(exc).__name__}: {exc}"[:200]
            logger.warning("provider %s failed for %s: %s", self.name, mint[:8], self._last_error)
            return None

    @abc.abstractmethod
    async def _fetch(self, mint: str) -> ProviderQuote | None:
        """Provider-specific fetch + parse. May raise; the wrapper contains it."""

    def status(self) -> ProviderStatus:
        """Monitoring snapshot of this provider."""
        ok_calls = self._calls - self._errors
        return ProviderStatus(
            name=self.name,
            configured=self.configured,
            calls=self._calls,
            errors=self._errors,
            avg_latency_ms=round(self._latency_total_ms / ok_calls, 1) if ok_calls else None,
            last_success=self._last_success,
            last_error=self._last_error,
        )
