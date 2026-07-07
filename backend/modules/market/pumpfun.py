"""Pump.fun discovery client — READ-ONLY meme-coin launch data.

Talks to pump.fun's frontend API (unofficial but public; verified live
2026-07-04). Because it is unofficial it can change or rate-limit at any
time, so every call is guarded the same way as the market providers:
rate-guarded, error-contained, stats-tracked, and failures surface as an
honest ExternalServiceError — never invented data.

This module must NEVER buy, sell, or sign anything (roadmap Stage 5 gate).
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

from config import Settings
from core.exceptions import ExternalServiceError, NotFoundError

logger = logging.getLogger(__name__)

_BASE_URL = "https://frontend-api-v3.pump.fun"
# Bonding curve starts with this many tokens in real reserves; progress
# toward graduation = share of them sold (community-documented constant).
_INITIAL_REAL_TOKEN_RESERVES = 793_100_000_000_000


class PumpCoin(BaseModel):
    """One pump.fun launch, normalized for the API."""

    mint: str
    name: str
    symbol: str
    created_at: datetime
    usd_market_cap: float | None = None
    reply_count: int = 0
    complete: bool = Field(description="True once graduated off the bonding curve")
    bonding_progress_pct: float = Field(description="0-100 toward graduation")
    is_currently_live: bool = False
    creator: str | None = None
    creator_username: str | None = None
    image_uri: str | None = None


def _parse_coin(raw: dict[str, Any]) -> PumpCoin:
    real_reserves = raw.get("real_token_reserves")
    if raw.get("complete"):
        progress = 100.0
    elif isinstance(real_reserves, (int, float)) and real_reserves >= 0:
        sold = _INITIAL_REAL_TOKEN_RESERVES - real_reserves
        progress = max(0.0, min(100.0, sold / _INITIAL_REAL_TOKEN_RESERVES * 100))
    else:
        progress = 0.0
    return PumpCoin(
        mint=raw["mint"],
        name=raw.get("name") or "",
        symbol=raw.get("symbol") or "",
        created_at=datetime.fromtimestamp(
            raw["created_timestamp"] / 1000, tz=timezone.utc
        ),
        usd_market_cap=raw.get("usd_market_cap"),
        reply_count=raw.get("reply_count") or 0,
        complete=bool(raw.get("complete")),
        bonding_progress_pct=round(progress, 1),
        is_currently_live=bool(raw.get("is_currently_live")),
        creator=raw.get("creator"),
        creator_username=raw.get("username"),
        image_uri=raw.get("image_uri"),
    )


class PumpFunClient:
    """Read-only pump.fun discovery: new launches, graduating, coin detail."""

    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        min_interval_s: float = 1.0,
        max_retries: int = 2,
    ) -> None:
        self._http = http or httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=15.0,
            # The frontend API expects a browser-ish UA; verified working.
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        self._min_interval = min_interval_s
        self._max_retries = max_retries
        self._last_call = 0.0
        self._calls = 0
        self._errors = 0

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # Same delay-not-drop rate guard as the market providers.
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()
        self._calls += 1

        # Retry transient failures (DNS/connect drops, 429, 5xx) with backoff
        # so a blip is absorbed instead of surfacing to the bots/UI. A 404 or
        # other 4xx is a real answer and is never retried.
        last_status: int | None = None
        for attempt in range(self._max_retries + 1):
            try:
                res = await self._http.get(path, params=params)
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(0.4 * (2**attempt))
                    continue
                self._errors += 1
                raise ExternalServiceError(
                    f"pump.fun unreachable: {type(exc).__name__}"
                ) from exc

            if res.status_code == 404:
                raise NotFoundError("pump.fun: coin not found")
            if res.status_code == 429 or res.status_code >= 500:
                last_status = res.status_code
                if attempt < self._max_retries:
                    await asyncio.sleep(0.4 * (2**attempt))
                    continue
            if res.status_code != 200:
                self._errors += 1
                raise ExternalServiceError(
                    f"pump.fun answered {res.status_code}",
                    details={"status": res.status_code or last_status},
                )
            return res.json()

        # Exhausted retries on a retryable status.
        self._errors += 1
        raise ExternalServiceError(
            f"pump.fun answered {last_status}", details={"status": last_status}
        )

    async def get_new_coins(self, limit: int = 20) -> list[PumpCoin]:
        """Freshest launches, newest first."""
        raw = await self._get(
            "/coins",
            {
                "offset": 0,
                "limit": limit,
                "sort": "created_timestamp",
                "order": "DESC",
                "includeNsfw": "false",
            },
        )
        return [_parse_coin(c) for c in raw]

    async def get_graduating(self, limit: int = 20) -> list[PumpCoin]:
        """Highest-cap coins still on the bonding curve (closest to graduation)."""
        raw = await self._get(
            "/coins",
            {
                "offset": 0,
                "limit": limit,
                "sort": "market_cap",
                "order": "DESC",
                "includeNsfw": "false",
                "complete": "false",
            },
        )
        return [_parse_coin(c) for c in raw]

    async def get_coin(self, mint: str) -> PumpCoin:
        """One launch by mint address."""
        raw = await self._get(f"/coins/{mint}")
        return _parse_coin(raw)

    def stats(self) -> dict[str, int]:
        return {"calls": self._calls, "errors": self._errors}

    async def aclose(self) -> None:
        await self._http.aclose()


_client: PumpFunClient | None = None


def get_pumpfun_client(settings: Settings) -> PumpFunClient:
    """Process-wide singleton, same pattern as the other modules."""
    global _client
    if _client is None:
        _client = PumpFunClient(
            min_interval_s=settings.market_provider_min_interval_seconds
        )
    return _client


async def close_pumpfun_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
