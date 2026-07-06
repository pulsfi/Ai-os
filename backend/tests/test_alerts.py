"""Alert service + endpoint tests. No network — Telegram stays unconfigured."""

from fastapi.testclient import TestClient

from config import Settings
from modules.alerts.service import AlertService


def test_emit_buffers_alert_without_telegram() -> None:
    svc = AlertService(Settings(_env_file=None))
    assert svc.telegram_configured is False
    alert = svc.emit("warning", "Test", "hello")
    assert alert.level == "warning"
    recent = svc.recent()
    assert recent[0].title == "Test"


def test_emit_newest_first_and_capped() -> None:
    svc = AlertService(Settings(_env_file=None))
    for i in range(5):
        svc.emit("info", f"a{i}", "m")
    assert [a.title for a in svc.recent()][:2] == ["a4", "a3"]


def test_telegram_configured_flag() -> None:
    svc = AlertService(
        Settings(_env_file=None, telegram_bot_token="t", telegram_chat_id="c")
    )
    assert svc.telegram_configured is True


def test_alerts_endpoints(client: TestClient) -> None:
    # Emit via the test endpoint, then read the feed back.
    emitted = client.post("/api/v1/alerts/test")
    assert emitted.status_code == 200
    assert emitted.json()["title"] == "Test alert"

    feed = client.get("/api/v1/alerts")
    assert feed.status_code == 200
    body = feed.json()
    assert body["telegram_configured"] is False
    assert any(a["title"] == "Test alert" for a in body["alerts"])


def test_kill_switch_emits_alert(client: TestClient) -> None:
    client.post("/api/v1/execution/kill/on")
    feed = client.get("/api/v1/alerts").json()
    assert any("Kill switch engaged" in a["title"] for a in feed["alerts"])
    client.post("/api/v1/execution/kill/off")
