"""Global error handling: every failure mode maps to the single envelope."""

from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.exceptions import NotFoundError


def _app_with_failing_route(settings: Settings):
    """Wire a scratch app with routes that raise, to exercise the handlers."""
    app = create_app(settings)

    @app.get("/boom-known")
    async def boom_known():
        raise NotFoundError("thing 42 does not exist")

    @app.get("/boom-unknown")
    async def boom_unknown():
        raise RuntimeError("secret internal detail")

    return app


def test_app_error_maps_to_envelope(settings: Settings) -> None:
    """AppError subclasses surface their code/message with the right status."""
    client = TestClient(_app_with_failing_route(settings))
    res = client.get("/boom-known")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"
    assert "42" in res.json()["error"]["message"]


def test_unexpected_error_is_opaque(settings: Settings) -> None:
    """Unhandled exceptions return 500 without leaking internals."""
    client = TestClient(_app_with_failing_route(settings), raise_server_exceptions=False)
    res = client.get("/boom-unknown")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"
    assert "secret" not in res.text
