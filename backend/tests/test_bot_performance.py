"""Performance endpoint + WebSocket stream tests (no network, no real fleet)."""

import pytest
from fastapi.testclient import TestClient

import api.v1.ws as ws_module
from config import Settings
from core.application import create_app
from core.dependencies import get_bots
from models.schemas.bots import (
    BotConfig,
    BotPerformance,
    BotState,
    BotStatus,
    BotTrade,
    EquityPoint,
)
from modules.bots.ledger import BotLedger


# --- equity-curve math through the real ledger -------------------------------


def test_ledger_curve_input_is_chronological(tmp_path) -> None:
    ledger = BotLedger(tmp_path / "bots.db")
    t1 = ledger.open_trade("sniper", "A", "AAA", 50.0, 1.0)
    t2 = ledger.open_trade("sniper", "B", "BBB", 50.0, 1.0)
    ledger.close_trade(t2, 1.2, "tp")  # closed first
    ledger.close_trade(t1, 0.9, "sl")
    closed = ledger.closed_trades_chrono("sniper")
    assert [t.mint for t in closed] == ["B", "A"] or [
        t.exit_ts for t in closed
    ] == sorted(t.exit_ts for t in closed)


# --- endpoint contracts -------------------------------------------------------


class StubManager:
    def performance(self) -> list[BotPerformance]:
        return [
            BotPerformance(
                bot_id="fleet",
                name="Whole fleet",
                closed_trades=2,
                wins=1,
                losses=1,
                win_rate_pct=50.0,
                realized_pnl_usd=5.0,
                avg_pnl_pct=5.0,
                best_trade_pct=20.0,
                worst_trade_pct=-10.0,
                curve=[
                    EquityPoint(ts="2026-07-05T00:00:00+00:00", equity_usd=10.0),
                    EquityPoint(ts="2026-07-05T01:00:00+00:00", equity_usd=5.0),
                ],
            )
        ]

    def statuses(self) -> list[BotStatus]:
        return [
            BotStatus(
                config=BotConfig(
                    id="sniper",
                    name="Launch Sniper",
                    strategy="new_launch_sniper",
                    description="d",
                    interval_s=20,
                    usd_per_trade=50,
                    max_open_positions=3,
                    take_profit_pct=40,
                    stop_loss_pct=25,
                    max_hold_s=900,
                ),
                state=BotState.RUNNING,
            )
        ]

    def trades(self, bot_id: str | None, limit: int) -> list[BotTrade]:
        return [
            BotTrade(
                id=1,
                bot_id="sniper",
                mint="MintA",
                symbol="AAA",
                usd_size=50.0,
                entry_price=1.0,
                entry_ts="2026-07-05T00:00:00+00:00",
                status="open",
            )
        ]


@pytest.fixture()
def stub_client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = create_app(settings)
    stub = StubManager()
    app.dependency_overrides[get_bots] = lambda: stub
    # The WS route resolves the manager itself (no Depends on websockets);
    # patch its accessor to the same stub.
    monkeypatch.setattr(ws_module, "get_bot_manager", lambda _settings: stub)
    with TestClient(app) as client:
        yield client


def test_performance_endpoint(stub_client: TestClient) -> None:
    res = stub_client.get("/api/v1/bots/performance")
    assert res.status_code == 200
    body = res.json()
    assert body[0]["bot_id"] == "fleet"
    assert body[0]["win_rate_pct"] == 50.0
    assert [p["equity_usd"] for p in body[0]["curve"]] == [10.0, 5.0]


def test_ws_pushes_fleet_snapshot(stub_client: TestClient) -> None:
    with stub_client.websocket_connect("/api/v1/ws") as socket:
        msg = socket.receive_json()
    assert msg["type"] == "fleet"
    assert msg["bots"][0]["config"]["id"] == "sniper"
    assert msg["bots"][0]["state"] == "running"
    assert msg["trades"][0]["symbol"] == "AAA"
