"""Jupiter adapter — price cross-check from the DEX aggregator's view."""

from modules.market.market_models import ProviderQuote
from modules.market.providers import MarketProvider


class JupiterProvider(MarketProvider):
    """https://lite-api.jup.ag — free lite tier, no key required."""

    name = "jupiter"

    async def _fetch(self, mint: str) -> ProviderQuote | None:
        res = await self._http.get(f"https://lite-api.jup.ag/price/v3?ids={mint}")
        res.raise_for_status()
        d = res.json().get(mint)
        if not d or d.get("usdPrice") is None:
            return None
        return ProviderQuote(
            provider=self.name,
            price_usd=float(d["usdPrice"]),
            change_24h=d.get("priceChange24h"),
            liquidity_usd=d.get("liquidity"),
        )
