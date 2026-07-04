"""Chat endpoint tests — no network, no real Claude API.

The streaming path is exercised through a stub service injected via
FastAPI dependency_overrides (the same seam the real wiring uses).
"""

import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_chat
from core.exceptions import ExternalServiceError
from modules.chat import ChatService


def test_chat_status_unconfigured(client: TestClient) -> None:
    """Without a key the status endpoint says so — no secrets leaked."""
    res = client.get("/api/v1/chat/status")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is False
    assert body["model"]  # model name is public config, fine to expose


def test_chat_post_unconfigured_returns_error_envelope(client: TestClient) -> None:
    """POST without a key fails fast with the standard envelope (no stream)."""
    res = client.post(
        "/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "configuration_error"
    assert "ANTHROPIC_API_KEY" in res.json()["error"]["message"]


def test_chat_post_validates_body(client: TestClient) -> None:
    """Empty conversations and bad roles are rejected before any work."""
    assert client.post("/api/v1/chat", json={"messages": []}).status_code == 422
    assert (
        client.post(
            "/api/v1/chat", json={"messages": [{"role": "system", "content": "x"}]}
        ).status_code
        == 422
    )


class _StubChatService:
    """Streams a canned reply through the real SSE encoding path."""

    is_configured = True
    model_name = "stub-model"

    def ensure_configured(self) -> None:  # configured stub: no-op
        return None

    async def stream_reply(self, messages: list[dict]) -> AsyncIterator[str]:
        assert messages[-1]["role"] == "user"
        for chunk in ("Hel", "lo ", "world"):
            yield chunk


class _FailingChatService(_StubChatService):
    async def stream_reply(self, messages: list[dict]) -> AsyncIterator[str]:
        yield "partial"
        raise ExternalServiceError("Claude API error (500)")


def _client_with(service: object, settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_chat] = lambda: service
    return TestClient(app)


def test_chat_post_streams_sse_deltas(settings: Settings) -> None:
    """A configured service streams delta frames and a final done frame."""
    with _client_with(_StubChatService(), settings) as client:
        res = client.post(
            "/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]}
        )
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        frames = [
            json.loads(line[6:])
            for line in res.text.split("\n")
            if line.startswith("data: ")
        ]
        deltas = [f["text"] for f in frames if f["type"] == "delta"]
        assert "".join(deltas) == "Hello world"
        assert frames[-1] == {"type": "done"}


def test_chat_post_midstream_failure_reports_error_frame(settings: Settings) -> None:
    """Errors after headers are sent arrive as an in-stream error frame."""
    with _client_with(_FailingChatService(), settings) as client:
        res = client.post(
            "/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]}
        )
        assert res.status_code == 200  # stream already committed
        frames = [
            json.loads(line[6:])
            for line in res.text.split("\n")
            if line.startswith("data: ")
        ]
        assert frames[0] == {"type": "delta", "text": "partial"}
        assert frames[-1]["type"] == "error"
        assert "Claude API error" in frames[-1]["message"]


def test_chat_service_gates_on_missing_key(settings: Settings) -> None:
    """The service itself refuses to build a client without a key."""
    service = ChatService(settings)
    assert service.is_configured is False
    try:
        service.ensure_configured()
        raise AssertionError("expected ConfigurationError")
    except Exception as exc:  # noqa: BLE001 — asserting on the type below
        assert type(exc).__name__ == "ConfigurationError"
