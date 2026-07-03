"""Market Intelligence — typed data contracts.

These Pydantic models are the module's public data language: providers
produce `ProviderQuote`s, the service merges them into `TokenMarketData`,
and every consumer (API, future agents) reads these shapes — never raw
provider JSON. Swapping a provider can therefore never break a consumer.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from models.schemas.solana import TokenAuthorities


class TradingPair(BaseModel):
    """One DEX pair a token trades on."""

    dex: str
    pair_address: str | None = None
    base_symbol: str | None = None
    quote_symbol: str | None = None
    price_usd: float | None = None
    liquidity_usd: float | None = None


class ProviderQuote(BaseModel):
    """What ONE provider knows about one token. All fields optional —
    providers report what they have; the merge fills the gaps."""

    provider: str
    price_usd: float | None = None
    change_24h: float | None = None
    volume_24h: float | None = None
    liquidity_usd: float | None = None
    market_cap: float | None = None
    fdv: float | None = None
    symbol: str | None = None
    dex: str | None = None
    pairs: list[TradingPair] = Field(default_factory=list)


class TokenMarketData(BaseModel):
    """The merged, validated market view of one token — the module's
    primary product, consumed by API and agents alike."""

    mint: str
    symbol: str | None
    price_usd: float | None
    change_24h: float | None
    volume_24h: float | None
    liquidity_usd: float | None
    market_cap: float | None
    fdv: float | None
    dex: str | None = Field(default=None, description="Deepest-liquidity DEX")
    pairs: list[TradingPair] = Field(default_factory=list)
    sources: list[str] = Field(description="Providers that contributed")
    divergence_pct: float | None = Field(
        default=None, description="Max cross-provider price disagreement (%)"
    )
    fetched_at: datetime


class TokenInfo(BaseModel):
    """Market data + on-chain metadata for GET /market/token/{address}."""

    market: TokenMarketData
    decimals: int | None = None
    supply_ui: float | None = None
    authorities: TokenAuthorities | None = Field(
        default=None, description="Mint/freeze authority state (rug signal)"
    )


class HistoryPoint(BaseModel):
    """One stored snapshot for GET /market/history/{address}."""

    ts: datetime
    price_usd: float | None
    change_24h: float | None
    volume_24h: float | None
    liquidity_usd: float | None
    market_cap: float | None
    fdv: float | None
    sources: str | None


class ProviderStatus(BaseModel):
    """Monitoring view of one provider (availability, latency, errors)."""

    name: str
    configured: bool
    calls: int
    errors: int
    avg_latency_ms: float | None
    last_success: datetime | None
    last_error: str | None


class MarketStatus(BaseModel):
    """GET /market/status — full module health for the Monitoring Agent."""

    providers: list[ProviderStatus]
    cache_backend: str
    cache_hits: int
    cache_misses: int
    scheduler_enabled: bool
    scheduler_interval_s: int
    scheduler_runs: int
    last_refresh: datetime | None
    tracked_tokens: int
