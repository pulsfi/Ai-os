"""/api/v1/market endpoints with a faked manager — no network, no DB."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_helius, get_market, get_solana_client
from core.exceptions import ExternalServiceError
from models.schemas.solana import TokenAuthorities
from modules.market.helius import TokenActivity
from modules.market.market_models import (
    HistoryPoint,
    MarketStatus,
    TokenInfo,
    TokenMarketData,
)

NOW = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)


def token_data(mint: str, change: float) -> TokenMarketData:
    return TokenMarketData(
        mint=mint,
        symbol="TOK",
        price_usd=1.0,
        change_24h=change,
        volume_24h=1e6,
        liquidity_usd=2e5,
        market_cap=9e6,
        fdv=1e7,
        sources=["dexscreener", "coingecko"],
        divergence_pct=0.5,
        fetched_at=NOW,
    )


class FakeManager:
    """Stands in for MarketManager behind the DI seam."""

    async def get_watchlist(self):
        return [token_data("MintA", 1.0), token_data("MintB", 9.0)]

    async def get_trending(self):
        return [token_data("MintB", 9.0), token_data("MintA", 1.0)]

    async def get_token_info(self, mint: str):
        return TokenInfo(market=token_data(mint, 1.0), decimals=9, supply_ui=1e9)

    async def get_history(self, mint: str, limit: int = 100):
        if mint == "dbdown":
            raise ExternalServiceError("history unavailable: database unreachable")
        return [HistoryPoint(ts=NOW, price_usd=1.0, change_24h=1.0, volume_24h=1e6,
                             liquidity_usd=2e5, market_cap=9e6, fdv=1e7, sources="dexscreener")]

    def status(self):
        return MarketStatus(
            providers=[], cache_backend="memory", cache_hits=3, cache_misses=1,
            scheduler_enabled=False, scheduler_interval_s=300, scheduler_runs=0,
            last_refresh=None, tracked_tokens=2,
        )


def make_client(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_market] = FakeManager
    return TestClient(app)


def test_tokens_endpoint(settings: Settings) -> None:
    res = make_client(settings).get("/api/v1/market/tokens")
    assert res.status_code == 200 and len(res.json()) == 2


def test_trending_orders_by_change(settings: Settings) -> None:
    body = make_client(settings).get("/api/v1/market/trending").json()
    assert [t["mint"] for t in body] == ["MintB", "MintA"]


def test_token_detail_includes_metadata(settings: Settings) -> None:
    body = make_client(settings).get("/api/v1/market/token/MintA").json()
    assert body["market"]["mint"] == "MintA" and body["decimals"] == 9


def test_history_endpoint(settings: Settings) -> None:
    body = make_client(settings).get("/api/v1/market/history/MintA").json()
    assert len(body) == 1 and body[0]["price_usd"] == 1.0


def test_history_db_down_maps_to_error_envelope(settings: Settings) -> None:
    """DB failure surfaces as the standard 502 envelope, not a raw 500."""
    res = make_client(settings).get("/api/v1/market/history/dbdown")
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "external_service_error"


def test_status_endpoint(settings: Settings) -> None:
    body = make_client(settings).get("/api/v1/market/status").json()
    assert body["cache_hits"] == 3 and body["tracked_tokens"] == 2


# --- /score/{mint} — the AI Decision Card engine -------------------------


class FakeHelius:
    """Configured Helius returning healthy buy-heavy flow."""

    is_configured = True

    async def get_token_activity(self, mint: str, limit: int = 40) -> TokenActivity:
        return TokenActivity(
            mint=mint, sampled_txs=40, swaps=30, buys=24, sells=6,
            buy_ratio_pct=80.0, unique_wallets=18,
        )


class FakeRpc:
    """Revoked mint + freeze authority (clean token)."""

    async def get_token_authorities(self, mint: str) -> TokenAuthorities:
        return TokenAuthorities(mint=mint, mint_authority=None, freeze_authority=None)


def score_client(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_market] = FakeManager
    app.dependency_overrides[get_helius] = FakeHelius
    app.dependency_overrides[get_solana_client] = FakeRpc
    return TestClient(app)


def test_score_endpoint_shape_and_signals(settings: Settings) -> None:
    body = score_client(settings).get("/api/v1/market/score/MintA").json()
    assert body["mint"] == "MintA"
    assert 0 <= body["score"] <= 100
    assert isinstance(body["factors"], list) and body["factors"]
    # Raw sub-signals wired through from the flow + authority checks.
    assert body["buy_ratio_pct"] == 80.0
    assert body["unique_wallets"] == 18
    assert body["mint_revoked"] is True and body["freeze_revoked"] is True


def test_score_healthy_token_is_approved(settings: Settings) -> None:
    body = score_client(settings).get("/api/v1/market/score/MintA").json()
    # Buy-heavy flow, many wallets, revoked authorities => passes the gate.
    assert body["approved"] is True and not body["rejects"]
