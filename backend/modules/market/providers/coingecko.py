"""CoinGecko adapter — general prices, market cap, 24h volume.

CoinGecko keys tokens by its own ids, not mints; the known-mint map
covers the default watchlist. TODO(market): resolve unknown mints via
CoinGecko's /coins/list?include_platform=true once needed.
"""

from modules.market.market_models import ProviderQuote
from modules.market.providers import MarketProvider

KNOWN_IDS: dict[str, str] = {
    "So11111111111111111111111111111111111111112": "solana",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "jupiter-exchange-solana",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "bonk",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "dogwifcoin",
}


class CoinGeckoProvider(MarketProvider):
    """https://api.coingecko.com — free tier, no key required."""

    name = "coingecko"

    async def _fetch(self, mint: str) -> ProviderQuote | None:
        cg_id = KNOWN_IDS.get(mint)
        if cg_id is None:
            return None  # unknown to this provider; others will cover it
        res = await self._http.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": cg_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
            },
        )
        res.raise_for_status()
        d = res.json().get(cg_id)
        if not d:
            return None
        return ProviderQuote(
            provider=self.name,
            price_usd=d.get("usd"),
            change_24h=d.get("usd_24h_change"),
            volume_24h=d.get("usd_24h_vol"),
            market_cap=d.get("usd_market_cap"),
        )
