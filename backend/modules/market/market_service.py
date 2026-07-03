"""Market service — merge, validate, and expose multi-provider data.

The heart of the module: takes whatever each provider knows and produces
ONE validated `TokenMarketData`, with cross-provider divergence checking
(the safeguard that caught the live JUP/JTO bad-pool incident).
"""

import asyncio
import logging

import httpx

from modules.market.market_models import ProviderQuote, TokenMarketData
from modules.market.providers import MarketProvider
from utils.time import utc_now

logger = logging.getLogger(__name__)

# Field preference order: DEX-level data beats aggregator estimates.
PRICE_PREFERENCE = ["dexscreener", "coingecko", "jupiter", "birdeye"]
DIVERGENCE_WARN_PCT = 2.0


class MarketService:
    """Fetch-and-merge orchestration over the provider set."""

    def __init__(self, providers: list[MarketProvider]) -> None:
        self._providers = providers

    async def fetch_token(self, mint: str) -> TokenMarketData:
        """Query every configured provider concurrently and merge."""
        quotes = [
            q
            for q in await asyncio.gather(*(p.get_quote(mint) for p in self._providers))
            if q is not None
        ]
        return self.merge(mint, quotes)

    def merge(self, mint: str, quotes: list[ProviderQuote]) -> TokenMarketData:
        """Combine provider quotes into the validated market view.

        Rules:
        - each field takes the first non-null value in PRICE_PREFERENCE order
        - price divergence across providers > 2% is logged as a warning and
          reported in the payload so consumers (Risk Agent) can react
        """
        by_name = {q.provider: q for q in quotes}
        ordered = [by_name[n] for n in PRICE_PREFERENCE if n in by_name]

        def first(field: str):  # noqa: ANN202 — heterogeneous fields
            for q in ordered:
                value = getattr(q, field)
                if value is not None:
                    return value
            return None

        prices = [q.price_usd for q in quotes if q.price_usd is not None]
        divergence = None
        if len(prices) >= 2:
            divergence = round((max(prices) - min(prices)) / min(prices) * 100, 2)
            if divergence > DIVERGENCE_WARN_PCT:
                logger.warning(
                    "price divergence %.2f%% for %s across %s",
                    divergence,
                    mint[:8],
                    [q.provider for q in quotes],
                )

        ds = by_name.get("dexscreener")
        return TokenMarketData(
            mint=mint,
            symbol=first("symbol"),
            price_usd=first("price_usd"),
            change_24h=first("change_24h"),
            volume_24h=first("volume_24h"),
            liquidity_usd=first("liquidity_usd"),
            market_cap=first("market_cap"),
            fdv=first("fdv"),
            dex=ds.dex if ds else None,
            pairs=ds.pairs if ds else [],
            sources=[q.provider for q in quotes],
            divergence_pct=divergence,
            fetched_at=utc_now(),
        )

    def provider_statuses(self):  # noqa: ANN201 — list[ProviderStatus]
        """Monitoring snapshots for every provider (configured or not)."""
        return [p.status() for p in self._providers]


def build_providers(settings, http: httpx.AsyncClient) -> list[MarketProvider]:  # noqa: ANN001
    """Assemble the provider set from configuration (the swap point)."""
    from modules.market.providers.birdeye import BirdeyeProvider
    from modules.market.providers.coingecko import CoinGeckoProvider
    from modules.market.providers.dexscreener import DexScreenerProvider
    from modules.market.providers.jupiter import JupiterProvider

    interval = settings.market_provider_min_interval_seconds
    return [
        DexScreenerProvider(http, interval),
        CoinGeckoProvider(http, interval),
        JupiterProvider(http, interval),
        BirdeyeProvider(http, settings.birdeye_api_key, interval),
    ]
