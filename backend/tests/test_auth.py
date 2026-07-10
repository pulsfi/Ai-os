"""API auth gate — off by default, enforced when a token is set."""

from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app


def test_no_token_means_open(client: TestClient) -> None:
    # Default test settings have no token -> API is open (health ok).
    assert client.get("/api/v1/health").status_code == 200


def test_token_required_when_set() -> None:
    app = create_app(Settings(_env_file=None, api_auth_token="secret", log_level="WARNING"))
    with TestClient(app) as c:
        # Health stays open (uptime monitors).
        assert c.get("/api/v1/health").status_code == 200
        # A protected route is 401 without the key.
        assert c.get("/api/v1/bots").status_code == 401
        # ...and 200 with it (header or bearer).
        assert c.get("/api/v1/bots", headers={"X-API-Key": "secret"}).status_code == 200
        assert (
            c.get("/api/v1/bots", headers={"Authorization": "Bearer secret"}).status_code
            == 200
        )
        # Wrong key -> 401 with the standard envelope.
        r = c.get("/api/v1/bots", headers={"X-API-Key": "nope"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"


def test_ws_requires_token_when_set() -> None:
    app = create_app(Settings(_env_file=None, api_auth_token="secret", log_level="WARNING"))
    with TestClient(app) as c:
        with c.websocket_connect("/api/v1/ws?token=secret") as ws:
            assert ws.receive_json()["type"] == "fleet"
