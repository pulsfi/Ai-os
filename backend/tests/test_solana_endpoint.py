"""/api/v1/solana endpoints via dependency override — no network."""

import json

import httpx
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_solana_client
from modules.solana.client import RpcClient


def _fake_rpc() -> RpcClient:
    """RpcClient answering canned mainnet-shaped responses."""

    def handler(req: httpx.Request) -> httpx.Response:
        method = json.loads(req.content)["method"]
        results = {
            "getHealth": "ok",
            "getSlot": 430_000_000,
            "getEpochInfo": {"epoch": 996, "slotIndex": 100, "slotsInEpoch": 432000, "absoluteSlot": 430000000},
            "getRecentPerformanceSamples": [{"numTransactions": 60000, "samplePeriodSecs": 20}],
        }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": results[method]})

    return RpcClient("http://rpc.test", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_solana_status_endpoint(settings: Settings) -> None:
    """GET /solana/status serializes the aggregated ChainStatus contract."""
    app = create_app(settings)
    app.dependency_overrides[get_solana_client] = _fake_rpc
    with TestClient(app) as client:
        res = client.get("/api/v1/solana/status")
    assert res.status_code == 200
    body = res.json()
    assert body["healthy"] is True
    assert body["slot"] == 430_000_000
    assert body["epoch"]["epoch"] == 996
    assert body["epoch"]["progress_pct"] == 0.0  # 100/432000 rounds to 0.0
    assert body["tps"] == 3000.0
