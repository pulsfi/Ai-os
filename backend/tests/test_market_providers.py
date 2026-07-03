"""Provider adapters: parsing, filtering, rate guard, key gating.

All against httpx.MockTransport — no network.
"""

import httpx

from modules.market.providers.birdeye import BirdeyeProvider
from modules.market.providers.coingecko import CoinGeckoProvider
from modules.market.providers.dexscreener import DexScreenerProvider


def http_with(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def ds_pair(quote_symbol: str, price: str, liq: float) -> dict:
    """Minimal DexScreener pair payload."""
    return {
        "chainId": "solana",
        "dexId": "orca",
        "pairAddress": "pair1",
        "baseToken": {"address": "MintA", "symbol": "TOK"},
        "quoteToken": {"symbol": quote_symbol},
        "priceUsd": price,
        "liquidity": {"usd": liq},
        "volume": {"h24": 1000.0},
        "priceChange": {"h24": 2.5},
        "fdv": 5_000_000,
    }


async def test_dexscreener_ignores_exotic_quote_pairs() -> None:
    """Regression for the live JUP/JTO incident: an exotic pair with huge
    liquidity and garbage priceUsd must lose to a major-quote pair."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"pairs": [ds_pair("JTO", "1237.65", 4_800_000), ds_pair("SOL", "0.24", 340_000)]},
        )

    provider = DexScreenerProvider(http_with(handler), min_interval_s=0)
    quote = await provider.get_quote("MintA")
    assert quote is not None
    assert quote.price_usd == 0.24  # the major-quote pair won


async def test_dexscreener_requires_base_token_match() -> None:
    """Pairs where the mint is the QUOTE side must be excluded."""

    def handler(req: httpx.Request) -> httpx.Response:
        pair = ds_pair("SOL", "9.99", 100_000)
        pair["baseToken"]["address"] = "SomeoneElse"
        return httpx.Response(200, json={"pairs": [pair]})

    provider = DexScreenerProvider(http_with(handler), min_interval_s=0)
    assert await provider.get_quote("MintA") is None


async def test_coingecko_parses_known_mint() -> None:
    """A watchlist mint maps to its CoinGecko id and parses all fields."""

    def handler(req: httpx.Request) -> httpx.Response:
        assert "solana" in str(req.url)
        return httpx.Response(
            200,
            json={"solana": {"usd": 80.5, "usd_24h_change": 3.2, "usd_market_cap": 4.7e10, "usd_24h_vol": 2e9}},
        )

    provider = CoinGeckoProvider(http_with(handler), min_interval_s=0)
    quote = await provider.get_quote("So11111111111111111111111111111111111111112")
    assert quote is not None and quote.price_usd == 80.5 and quote.market_cap == 4.7e10


async def test_birdeye_skipped_without_key() -> None:
    """Unconfigured Birdeye returns None without making any HTTP call."""
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    provider = BirdeyeProvider(http_with(handler), api_key="", min_interval_s=0)
    assert provider.configured is False
    assert await provider.get_quote("MintA") is None
    assert calls == 0


async def test_rate_guard_delays_rapid_calls() -> None:
    """A second call inside min_interval is delayed to the provider's pace —
    data is never dropped (live lesson: skipping lost 3 of 4 tokens)."""
    import time

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pairs": [ds_pair("SOL", "1.0", 1000)]})

    provider = DexScreenerProvider(http_with(handler), min_interval_s=0.3)
    start = time.monotonic()
    assert await provider.get_quote("MintA") is not None
    assert await provider.get_quote("MintA") is not None  # delayed, not lost
    assert time.monotonic() - start >= 0.3  # the guard actually paced us


async def test_provider_stats_track_errors() -> None:
    """Failures increment error counters and record the last error."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=req)

    provider = DexScreenerProvider(http_with(handler), min_interval_s=0)
    assert await provider.get_quote("MintA") is None
    status = provider.status()
    assert status.errors == 1 and status.calls == 1
    assert "ConnectError" in (status.last_error or "")
