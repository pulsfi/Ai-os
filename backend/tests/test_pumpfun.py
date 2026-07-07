"""Pump.fun client tests — mocked transport, no network."""

import httpx
import pytest
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_pumpfun
from core.exceptions import ExternalServiceError, NotFoundError
from modules.market.pumpfun import (
    _INITIAL_REAL_TOKEN_RESERVES,
    PumpFunClient,
)


def coin_payload(**overrides) -> dict:
    base = {
        "mint": "MintAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaapump",
        "name": "Test Coin",
        "symbol": "TEST",
        "created_timestamp": 1_751_600_000_000,
        "usd_market_cap": 5000.0,
        "reply_count": 3,
        "complete": False,
        "real_token_reserves": _INITIAL_REAL_TOKEN_RESERVES // 2,
        "is_currently_live": False,
        "creator": "CreatorAddr",
        "username": "tester",
        "image_uri": "https://ipfs.io/x",
    }
    base.update(overrides)
    return base


def client_with(handler, max_retries: int = 0) -> PumpFunClient:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    )
    return PumpFunClient(http, min_interval_s=0.0, max_retries=max_retries)


async def test_new_coins_parsed_and_progress_computed() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params["sort"] == "created_timestamp"
        return httpx.Response(200, json=[coin_payload()])

    coins = await client_with(handler).get_new_coins(limit=5)
    assert len(coins) == 1
    coin = coins[0]
    assert coin.symbol == "TEST"
    assert coin.bonding_progress_pct == 50.0  # half the curve sold
    assert coin.complete is False


async def test_graduated_coin_reports_full_progress() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[coin_payload(complete=True, real_token_reserves=0)]
        )

    coins = await client_with(handler).get_graduating()
    assert coins[0].bonding_progress_pct == 100.0
    assert coins[0].complete is True


async def test_missing_coin_raises_not_found() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "nope"})

    with pytest.raises(NotFoundError):
        await client_with(handler).get_coin("UnknownMint")


async def test_upstream_failure_is_external_service_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(530)

    client = client_with(handler)
    with pytest.raises(ExternalServiceError):
        await client.get_new_coins()
    assert client.stats()["errors"] == 1


async def test_transient_blip_is_retried_and_recovers() -> None:
    """A DNS/connect blip on the first try is absorbed by a retry."""
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("getaddrinfo failed")
        return httpx.Response(200, json=[coin_payload()])

    client = client_with(handler, max_retries=2)
    coins = await client.get_new_coins()
    assert len(coins) == 1  # recovered
    assert calls["n"] == 2  # failed once, retried, succeeded
    assert client.stats()["errors"] == 0  # a recovered blip isn't an error


def test_endpoints_return_normalized_coins(settings: Settings) -> None:
    """The /market/pumpfun routes serve the normalized model."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[coin_payload()])

    app = create_app(settings)
    app.dependency_overrides[get_pumpfun] = lambda: client_with(handler)
    with TestClient(app) as client:
        res = client.get("/api/v1/market/pumpfun/new")
        assert res.status_code == 200
        body = res.json()
        assert body[0]["mint"].endswith("pump")
        assert body[0]["bonding_progress_pct"] == 50.0
        # limit is validated
        assert client.get("/api/v1/market/pumpfun/new?limit=0").status_code == 422
