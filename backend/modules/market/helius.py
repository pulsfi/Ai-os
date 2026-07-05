"""Helius Enhanced Transactions client — READ-ONLY token activity.

Uses the Helius parsed-transaction API (api.helius.xyz/v0) to answer one
question the price feeds cannot: WHO is trading a token right now?
From the latest parsed transactions we derive buy/sell counts, unique
wallets, and transaction rate — the flow signal behind a price move.

Key-gated like every optional provider: no HELIUS_API_KEY = the endpoint
reports "not configured" instead of pretending. Never signs, never sends.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

from config import Settings
from core.exceptions import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.helius.xyz"


class TokenActivity(BaseModel):
    """Flow summary derived from the latest parsed transactions."""

    mint: str
    sampled_txs: int = Field(description="Parsed transactions inspected")
    swaps: int = 0
    buys: int = 0  # swaps where the wallet RECEIVED this mint
    sells: int = 0  # swaps where the wallet SPENT this mint
    buy_ratio_pct: float | None = Field(
        default=None, description="buys / classified swaps, 0-100"
    )
    unique_wallets: int = 0
    txs_per_minute: float | None = None
    first_ts: str | None = None
    last_ts: str | None = None


def _classify_swap(tx: dict[str, Any], mint: str) -> str | None:
    """'buy' | 'sell' | None from the parsed swap event's token legs."""
    swap = (tx.get("events") or {}).get("swap") or {}
    for leg in swap.get("tokenOutputs") or []:
        if leg.get("mint") == mint:
            return "buy"
    for leg in swap.get("tokenInputs") or []:
        if leg.get("mint") == mint:
            return "sell"
    return None


class HeliusClient:
    """Read-only Helius Enhanced Transactions access (rate-guarded)."""

    def __init__(
        self,
        api_key: str,
        http: httpx.AsyncClient | None = None,
        min_interval_s: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._http = http or httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0)
        self._min_interval = min_interval_s
        self._last_call = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def ensure_configured(self) -> None:
        if not self.is_configured:
            raise ConfigurationError(
                "Token activity is not configured: set HELIUS_API_KEY in backend/.env",
                details={"setting": "HELIUS_API_KEY"},
            )

    async def get_token_activity(self, mint: str, limit: int = 50) -> TokenActivity:
        """Summarize the token's most recent parsed transactions."""
        self.ensure_configured()
        # Same delay-not-drop rate guard as the other providers.
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()
        try:
            res = await self._http.get(
                f"/v0/addresses/{mint}/transactions",
                params={"api-key": self._api_key, "limit": limit},
            )
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"Helius unreachable: {type(exc).__name__}"
            ) from exc
        if res.status_code != 200:
            raise ExternalServiceError(
                f"Helius answered {res.status_code}",
                details={"status": res.status_code},
            )
        txs: list[dict[str, Any]] = res.json()

        swaps = buys = sells = 0
        wallets: set[str] = set()
        timestamps: list[int] = []
        for tx in txs:
            ts = tx.get("timestamp")
            if isinstance(ts, int):
                timestamps.append(ts)
            fee_payer = tx.get("feePayer")
            if isinstance(fee_payer, str):
                wallets.add(fee_payer)
            if tx.get("type") == "SWAP":
                swaps += 1
                side = _classify_swap(tx, mint)
                if side == "buy":
                    buys += 1
                elif side == "sell":
                    sells += 1

        classified = buys + sells
        rate: float | None = None
        if len(timestamps) >= 2:
            span_s = max(timestamps) - min(timestamps)
            if span_s > 0:
                rate = round(len(timestamps) / (span_s / 60), 2)

        def iso(ts: int) -> str:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(
                timespec="seconds"
            )

        return TokenActivity(
            mint=mint,
            sampled_txs=len(txs),
            swaps=swaps,
            buys=buys,
            sells=sells,
            buy_ratio_pct=round(buys / classified * 100, 1) if classified else None,
            unique_wallets=len(wallets),
            txs_per_minute=rate,
            first_ts=iso(min(timestamps)) if timestamps else None,
            last_ts=iso(max(timestamps)) if timestamps else None,
        )

    async def aclose(self) -> None:
        await self._http.aclose()


_client: HeliusClient | None = None


def get_helius_client(settings: Settings) -> HeliusClient:
    """Process-wide singleton, same pattern as the other providers."""
    global _client
    if _client is None:
        _client = HeliusClient(
            settings.helius_api_key,
            min_interval_s=settings.market_provider_min_interval_seconds,
        )
    return _client


async def close_helius_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
