"""Execution-layer tests: risk engine, dry-run executor, readiness, endpoints.

The safety guarantees are the point here: disarmed by default, hard caps
enforced, kill switch halts, daily loss halts, and the live path is
unavailable. No network (Jupiter quote is mocked), no keys anywhere.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_bots, get_exec, get_risk
from models.schemas.bots import BotPerformance
from models.schemas.execution import OrderRequest, RiskLimits
from modules.execution.executor import DryRunExecutor, LiveExecutor
from modules.execution.readiness import evaluate_readiness
from modules.execution.risk_engine import RiskEngine


def make_engine(armed: bool = True, **overrides) -> RiskEngine:
    limits = RiskLimits(
        max_position_usd=overrides.get("max_position_usd", 10.0),
        daily_loss_limit_usd=overrides.get("daily_loss_limit_usd", 25.0),
        max_concurrent_positions=overrides.get("max_concurrent_positions", 2),
        max_slippage_bps=150,
    )
    return RiskEngine(limits=limits, armed=armed)


# --- risk engine -------------------------------------------------------------


def test_disarmed_by_default_blocks_everything() -> None:
    engine = make_engine(armed=False)
    assert engine.check_order(5.0, "buy").allowed is False
    assert "disarmed" in engine.check_order(5.0, "buy").reason


def test_position_cap_enforced() -> None:
    engine = make_engine()
    assert engine.check_order(10.0, "buy").allowed is True
    d = engine.check_order(10.01, "buy")
    assert d.allowed is False and "exceeds max position" in d.reason


def test_concurrency_cap_enforced() -> None:
    engine = make_engine(max_concurrent_positions=1)
    assert engine.check_order(5.0, "buy").allowed is True
    engine.record_open()
    assert engine.check_order(5.0, "buy").allowed is False


def test_daily_loss_limit_halts_trading() -> None:
    engine = make_engine(daily_loss_limit_usd=20.0)
    engine.record_open()
    engine.record_close(-20.0)  # hit the limit
    d = engine.check_order(5.0, "buy")
    assert d.allowed is False and "daily loss limit" in d.reason


def test_kill_switch_halts_and_releases() -> None:
    engine = make_engine()
    engine.set_kill_switch(True)
    assert engine.check_order(5.0, "buy").allowed is False
    engine.set_kill_switch(False)
    assert engine.check_order(5.0, "buy").allowed is True


# --- dry-run executor ----------------------------------------------------------


def executor_with_quote(engine: RiskEngine, quote: dict | None) -> DryRunExecutor:
    def handler(req: httpx.Request) -> httpx.Response:
        if quote is None:
            return httpx.Response(500, json={})
        return httpx.Response(200, json=quote)

    return DryRunExecutor(
        engine, http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


async def test_dry_run_fetches_quote_and_simulates_fill() -> None:
    engine = make_engine()
    execu = executor_with_quote(
        engine, {"outAmount": "1000000000", "priceImpactPct": "0.012"}
    )
    result = await execu.execute(
        OrderRequest(mint="M", symbol="AAA", side="buy", usd_size=5.0)
    )
    assert result.accepted is True
    assert result.mode.value == "dry_run"
    assert result.price_impact_pct == pytest.approx(1.2)
    assert "No transaction was built, signed, or sent" in result.detail
    await execu.aclose()


async def test_dry_run_blocked_by_risk_is_not_executed() -> None:
    engine = make_engine(armed=False)  # disarmed
    execu = executor_with_quote(engine, {"outAmount": "1", "priceImpactPct": "0"})
    result = await execu.execute(
        OrderRequest(mint="M", symbol="AAA", side="buy", usd_size=5.0)
    )
    assert result.accepted is False
    assert "blocked by risk engine" in result.detail
    await execu.aclose()


async def test_dry_run_survives_quote_failure() -> None:
    engine = make_engine()
    execu = executor_with_quote(engine, None)  # quote endpoint 500s
    result = await execu.execute(
        OrderRequest(mint="M", symbol="AAA", side="buy", usd_size=5.0)
    )
    assert result.accepted is True  # order still recorded
    assert "nothing sent" in result.detail
    await execu.aclose()


async def test_live_executor_is_unavailable() -> None:
    from modules.execution.executor import LiveExecutionUnavailable

    with pytest.raises(LiveExecutionUnavailable):
        await LiveExecutor().execute(
            OrderRequest(mint="M", symbol="AAA", side="buy", usd_size=5.0)
        )


# --- readiness ------------------------------------------------------------------


def test_readiness_not_ready_on_empty_record(settings: Settings) -> None:
    card = evaluate_readiness(None, None, settings)
    assert card.ready is False
    assert all(not c.passed for c in card.criteria)


def test_readiness_all_green(settings: Settings) -> None:
    from datetime import datetime, timedelta, timezone

    fleet = BotPerformance(
        bot_id="fleet",
        name="Whole fleet",
        closed_trades=60,
        wins=36,
        losses=24,
        win_rate_pct=60.0,
        realized_pnl_usd=40.0,
    )
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    card = evaluate_readiness(fleet, old, settings)
    assert card.ready is True
    assert all(c.passed for c in card.criteria)


# --- endpoints ------------------------------------------------------------------


class StubBots:
    def performance(self):
        return [BotPerformance(bot_id="fleet", name="Fleet", closed_trades=3)]

    def first_entry_ts(self):
        return None


@pytest.fixture()
def exec_client(settings: Settings) -> TestClient:
    app = create_app(settings)
    engine = make_engine(armed=False)
    app.dependency_overrides[get_risk] = lambda: engine
    app.dependency_overrides[get_exec] = lambda: executor_with_quote(
        engine, {"outAmount": "1000000000", "priceImpactPct": "0.01"}
    )
    app.dependency_overrides[get_bots] = lambda: StubBots()
    with TestClient(app) as client:
        yield client


def test_status_reports_disarmed(exec_client: TestClient) -> None:
    res = exec_client.get("/api/v1/execution/status")
    assert res.status_code == 200
    body = res.json()
    assert body["armed"] is False
    assert body["live_available"] is False
    assert body["mode"] == "dry_run"


def test_kill_switch_endpoint_only_halts(exec_client: TestClient) -> None:
    on = exec_client.post("/api/v1/execution/kill/on").json()
    assert on["kill_switch"] is True
    off = exec_client.post("/api/v1/execution/kill/off").json()
    assert off["kill_switch"] is False


def test_readiness_endpoint(exec_client: TestClient) -> None:
    res = exec_client.get("/api/v1/execution/readiness")
    assert res.status_code == 200
    assert res.json()["ready"] is False


def test_dry_run_endpoint_blocked_when_disarmed(exec_client: TestClient) -> None:
    res = exec_client.post(
        "/api/v1/execution/dry-run",
        json={"mint": "M", "symbol": "AAA", "side": "buy", "usd_size": 5.0},
    )
    assert res.status_code == 200
    assert res.json()["accepted"] is False  # disarmed -> risk engine blocks
