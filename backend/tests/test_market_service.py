"""MarketService merge logic: preference order, divergence, gaps."""

from modules.market.market_models import ProviderQuote
from modules.market.market_service import MarketService


def q(provider: str, **fields) -> ProviderQuote:
    return ProviderQuote(provider=provider, **fields)


def test_merge_prefers_dex_data_and_fills_gaps() -> None:
    """DexScreener wins for price; CoinGecko fills the market-cap gap."""
    svc = MarketService(providers=[])
    data = svc.merge(
        "MintA",
        [
            q("coingecko", price_usd=1.02, market_cap=9e6, volume_24h=5e5),
            q("dexscreener", price_usd=1.00, liquidity_usd=2e5, symbol="TOK", dex="orca"),
        ],
    )
    assert data.price_usd == 1.00  # dexscreener preferred
    assert data.market_cap == 9e6  # gap filled by coingecko
    assert data.symbol == "TOK" and data.dex == "orca"
    assert set(data.sources) == {"coingecko", "dexscreener"}


def test_merge_computes_divergence() -> None:
    """A 2% spread across providers is reported to consumers."""
    svc = MarketService(providers=[])
    data = svc.merge("MintA", [q("dexscreener", price_usd=1.00), q("jupiter", price_usd=1.02)])
    assert data.divergence_pct == 2.0


def test_merge_with_no_quotes_is_empty_but_valid() -> None:
    """Zero provider data yields an empty (sources=[]) payload, not a crash."""
    svc = MarketService(providers=[])
    data = svc.merge("MintA", [])
    assert data.sources == [] and data.price_usd is None
