"""Health and system endpoints.

The suite runs WITHOUT PostgreSQL/Redis: /health must respond 200 and
report those components as down/degraded rather than failing — that
resilience is itself the behavior under test.
"""

from fastapi.testclient import TestClient


def test_ping_is_cheap_and_ok(client: TestClient) -> None:
    """Liveness endpoint always answers ok."""
    res = client.get("/api/v1/ping")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_reports_all_components(client: TestClient) -> None:
    """/health returns 200 with a full component list even when infra is down."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    names = {c["name"] for c in body["components"]}
    assert {"api", "database", "redis", "solana_rpc"} <= names
    assert body["status"] in {"ok", "degraded"}  # degraded when infra is absent
    api = next(c for c in body["components"] if c["name"] == "api")
    assert api["status"] == "ok"


def test_system_info_exposes_identity(client: TestClient) -> None:
    """/system/info returns typed, non-sensitive identity fields."""
    res = client.get("/api/v1/system/info")
    assert res.status_code == 200
    body = res.json()
    assert body["app_name"] == "os-ai-backend"
    assert body["environment"] == "development"
