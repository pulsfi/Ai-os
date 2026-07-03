"""DexScreener adapter — DEX pairs: price, liquidity, volume, FDV.

Lesson baked in from the live 2026-07-02 incident: exotic quote pairs
(e.g. JUP/JTO) report garbage priceUsd, so only pairs quoted in majors
are trusted. See tests/test_market_providers.py for the regression test.
"""

import httpx

from modules.market.market_models import ProviderQuote, TradingPair
from modules.market.providers import MarketProvider

MAJOR_QUOTES = {"SOL", "WSOL", "USDC", "USDT"}


class DexScreenerProvider(MarketProvider):
    """https://api.dexscreener.com — free, no key."""

    name = "dexscreener"

    async def _fetch(self, mint: str) -> ProviderQuote | None:
        res = await self._http.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}")
        res.raise_for_status()
        pairs = [
            p
            for p in (res.json().get("pairs") or [])
            if p.get("chainId") == "solana" and p.get("baseToken", {}).get("address") == mint
        ]
        major = [p for p in pairs if p.get("quoteToken", {}).get("symbol") in MAJOR_QUOTES]
        if major:
            pairs = major
        if not pairs:
            return None
        best = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        return ProviderQuote(
            provider=self.name,
            price_usd=float(best["priceUsd"]) if best.get("priceUsd") else None,
            change_24h=(best.get("priceChange") or {}).get("h24"),
            volume_24h=(best.get("volume") or {}).get("h24"),
            liquidity_usd=(best.get("liquidity") or {}).get("usd"),
            fdv=best.get("fdv"),
            symbol=best.get("baseToken", {}).get("symbol"),
            dex=best.get("dexId"),
            pairs=[
                TradingPair(
                    dex=p.get("dexId", "?"),
                    pair_address=p.get("pairAddress"),
                    base_symbol=p.get("baseToken", {}).get("symbol"),
                    quote_symbol=p.get("quoteToken", {}).get("symbol"),
                    price_usd=float(p["priceUsd"]) if p.get("priceUsd") else None,
                    liquidity_usd=(p.get("liquidity") or {}).get("usd"),
                )
                for p in pairs[:10]
            ],
        )
