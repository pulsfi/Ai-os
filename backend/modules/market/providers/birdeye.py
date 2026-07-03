"""Birdeye adapter — token prices. OPTIONAL: needs a free API key.

Unconfigured (no key) => `configured` is False and the base class skips
it silently; the module runs on the four keyless providers.
"""

import httpx

from modules.market.market_models import ProviderQuote
from modules.market.providers import MarketProvider


class BirdeyeProvider(MarketProvider):
    """https://public-api.birdeye.so — set BIRDEYE_API_KEY to enable."""

    name = "birdeye"

    def __init__(self, http: httpx.AsyncClient, api_key: str, min_interval_s: float = 1.0) -> None:
        super().__init__(http, min_interval_s)
        self._api_key = api_key.strip()

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def _fetch(self, mint: str) -> ProviderQuote | None:
        res = await self._http.get(
            "https://public-api.birdeye.so/defi/price",
            params={"address": mint},
            headers={"X-API-KEY": self._api_key, "x-chain": "solana"},
        )
        res.raise_for_status()
        value = (res.json().get("data") or {}).get("value")
        if value is None:
            return None
        return ProviderQuote(provider=self.name, price_usd=float(value))
