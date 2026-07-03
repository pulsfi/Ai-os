"""Market cache — Redis with transparent in-memory fallback.

The cache is what keeps us inside provider rate limits: reads inside the
TTL window never touch a provider. Redis being down must not take the
module down (lazy-optional infrastructure, Decision 6), so a per-process
dict takes over transparently and /market/status reports which backend
is live.
"""

import json
import logging
import time
from typing import Any

from config import Settings
from database.redis_client import get_redis

logger = logging.getLogger(__name__)


class MarketCache:
    """TTL cache for merged token data; hit/miss counters for monitoring."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ttl = settings.market_cache_ttl_seconds
        self._memory: dict[str, tuple[float, Any]] = {}
        self._redis_ok = True  # optimistic until a failure flips it
        self.hits = 0
        self.misses = 0

    @property
    def backend(self) -> str:
        """Which backend served the last operations ('redis' or 'memory')."""
        return "redis" if self._redis_ok else "memory"

    async def get(self, key: str) -> Any | None:
        """Return the cached value or None; counts hits/misses."""
        value = await self._redis_get(key)
        if value is None and not self._redis_ok:
            entry = self._memory.get(key)
            if entry and entry[0] > time.monotonic():
                value = entry[1]
        if value is not None:
            self.hits += 1
            logger.debug("cache hit %s", key)
        else:
            self.misses += 1
        return value

    async def set(self, key: str, value: Any) -> None:
        """Store a JSON-serializable value under the configured TTL."""
        payload = json.dumps(value, default=str)
        if self._redis_ok:
            try:
                await get_redis(self._settings).set(key, payload, ex=self._ttl)
                return
            except Exception as exc:  # noqa: BLE001 — degrade, don't die
                self._redis_ok = False
                logger.warning("Redis unavailable (%s) — falling back to memory cache", exc)
        self._memory[key] = (time.monotonic() + self._ttl, value)

    async def _redis_get(self, key: str) -> Any | None:
        if not self._redis_ok:
            return None
        try:
            raw = await get_redis(self._settings).get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            self._redis_ok = False
            logger.warning("Redis unavailable (%s) — falling back to memory cache", exc)
            return None
