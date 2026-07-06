"""Bot fleet tests — ledger, strategies, runner lifecycle, endpoints.

No network: strategies run against stub pump.fun/market clients, and
endpoint tests inject a stub manager via dependency_overrides.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_bots
from models.schemas.bots import BotConfig, BotControlResult, BotState, BotStatus
from modules.bots.ledger import BotLedger
from modules.bots.runner import BotRunner
from modules.bots.strategies import EntrySignal, NewLaunchSniper, Strategy
from modules.market.pumpfun import PumpCoin


# --- ledger -----------------------------------------------------------------


def make_ledger(tmp_path: Path) -> BotLedger:
    return BotLedger(tmp_path / "bots.db")


def test_ledger_open_close_and_stats(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    t1 = ledger.open_trade("sniper", "MintA", "AAA", 50.0, 0.00001, "test entry")
    t2 = ledger.open_trade("sniper", "MintB", "BBB", 50.0, 0.00002)
    assert [t.mint for t in ledger.open_trades("sniper")] == ["MintA", "MintB"]

    ledger.close_trade(t1, 0.000014, "take-profit +40%")  # +40%
    ledger.close_trade(t2, 0.000015, "stop-loss -25%")  # -25%

    stats = ledger.stats("sniper")
    assert stats["open_positions"] == 0
    assert stats["closed_trades"] == 2
    assert stats["win_rate_pct"] == 50.0
    # +40% and -25% of $50: +20 - 12.5 = +7.5
    assert stats["realized_pnl_usd"] == pytest.approx(7.5, abs=0.01)

    trades = ledger.trades("sniper")
    assert trades[0].status == "closed"
    assert trades[0].pnl_pct is not None


def test_ledger_reset_wipes_all(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    ledger.open_trade("sniper", "A", "AAA", 50.0, 1.0)
    ledger.open_trade("trend", "B", "BBB", 50.0, 1.0)
    assert ledger.reset() == 2
    assert ledger.trades(None, 10) == []
    assert ledger.first_entry_ts() is None


def test_ledger_isolates_bots(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    ledger.open_trade("sniper", "MintA", "AAA", 50.0, 1.0)
    ledger.open_trade("trend", "MintB", "BBB", 50.0, 1.0)
    assert len(ledger.open_trades("sniper")) == 1
    assert ledger.stats("trend")["open_positions"] == 1
    assert len(ledger.trades(None, 10)) == 2


# --- strategies ---------------------------------------------------------------


def pump_coin(
    mint: str,
    mcap: float | None,
    age_s: float = 30.0,
    replies: int = 3,
    complete: bool = False,
    progress: float = 10.0,
) -> PumpCoin:
    return PumpCoin(
        mint=mint,
        name=mint,
        symbol=mint[:4].upper(),
        created_at=datetime.now(timezone.utc) - timedelta(seconds=age_s),
        usd_market_cap=mcap,
        reply_count=replies,
        complete=complete,
        bonding_progress_pct=progress,
        is_currently_live=True,
    )


class StubPumpFun:
    def __init__(self, coins: list[PumpCoin]) -> None:
        self._coins = coins

    async def get_new_coins(self, limit: int = 20) -> list[PumpCoin]:
        return self._coins[:limit]

    async def get_graduating(self, limit: int = 20) -> list[PumpCoin]:
        return self._coins[:limit]

    async def get_coin(self, mint: str) -> PumpCoin:
        for c in self._coins:
            if c.mint == mint:
                return c
        raise AssertionError("not found")


async def test_graduation_entry_band_excludes_late_entries() -> None:
    """Regression for the 2026-07-04 track record: 100%-progress entries
    lost 0/3 — the band must exclude coins that already graduated."""
    from modules.bots.strategies import GraduationMomentum

    coins = [
        pump_coin("TooEarly", 50_000, progress=60.0),
        pump_coin("InBand", 50_000, progress=92.0),
        pump_coin("TooLate", 50_000, progress=99.9),
        pump_coin("AtTop", 50_000, progress=100.0),
        pump_coin("Complete", 50_000, progress=100.0, complete=True),
    ]
    strat = GraduationMomentum(StubPumpFun(coins), market=None)  # type: ignore[arg-type]
    signals = await strat.find_entries(held_mints=set(), slots=5)
    assert [s.mint for s in signals] == ["InBand"]


async def test_sniper_filters_and_prices() -> None:
    coins = [
        pump_coin("Fresh1", 10_000),                 # good
        pump_coin("TooOld", 10_000, age_s=600),      # too old
        pump_coin("TooSmall", 2_000),                # below mcap floor
        pump_coin("NoReplies", 10_000, replies=0),   # no traction
        pump_coin("Done", 10_000, complete=True),    # graduated
        pump_coin("Fresh2", 20_000),                 # good
    ]
    sniper = NewLaunchSniper(StubPumpFun(coins), market=None)  # type: ignore[arg-type]
    signals = await sniper.find_entries(held_mints=set(), slots=5)
    assert [s.mint for s in signals] == ["Fresh1", "Fresh2"]
    # price = mcap / 1B fixed supply
    assert signals[0].price_usd == pytest.approx(10_000 / 1_000_000_000)
    # held mints are excluded
    signals = await sniper.find_entries(held_mints={"Fresh1"}, slots=5)
    assert [s.mint for s in signals] == ["Fresh2"]


# --- runner ----------------------------------------------------------------


class ScriptedStrategy(Strategy):
    """Enters MintX once, then reports whatever price the test sets."""

    name = "scripted"

    def __init__(self) -> None:  # no clients needed
        self.price: float | None = 1.0
        self.entered = False

    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        if self.entered or "MintX" in held_mints or slots < 1:
            return []
        self.entered = True
        return [EntrySignal("MintX", "XXX", 1.0, "scripted entry")]

    async def current_price(self, mint: str) -> float | None:
        return self.price


def make_runner(tmp_path: Path, **overrides: object) -> tuple[BotRunner, ScriptedStrategy]:
    config = BotConfig(
        id="testbot",
        name="Test Bot",
        strategy="scripted",
        description="test",
        interval_s=0.05,
        usd_per_trade=100.0,
        max_open_positions=1,
        take_profit_pct=10.0,
        stop_loss_pct=10.0,
        max_hold_s=3600.0,
        **overrides,  # type: ignore[arg-type]
    )
    strategy = ScriptedStrategy()
    # No haircut/cap here — these tests assert exact PnL from the exit logic.
    return (
        BotRunner(
            config, strategy, make_ledger(tmp_path),
            exit_slippage_bps=0, max_gain_pct=1_000_000.0,
        ),
        strategy,
    )


async def test_runner_opens_then_takes_profit(tmp_path: Path) -> None:
    runner, strategy = make_runner(tmp_path)
    await runner.tick()  # opens MintX @ 1.0
    status = runner.status()
    assert status.open_positions == 1

    strategy.price = 1.15  # +15% > 10% take-profit
    await runner.tick()
    status = runner.status()
    assert status.open_positions == 0
    assert status.closed_trades == 1
    assert status.realized_pnl_usd == pytest.approx(15.0, abs=0.01)
    assert status.win_rate_pct == 100.0


async def test_runner_stop_loss(tmp_path: Path) -> None:
    runner, strategy = make_runner(tmp_path)
    await runner.tick()
    strategy.price = 0.85  # -15% < -10% stop
    await runner.tick()
    status = runner.status()
    assert status.closed_trades == 1
    assert status.realized_pnl_usd == pytest.approx(-15.0, abs=0.01)


async def test_runner_start_stop_lifecycle(tmp_path: Path) -> None:
    runner, _ = make_runner(tmp_path)
    assert runner.start() is True
    assert runner.start() is False  # already running
    assert runner.status().state == BotState.RUNNING
    assert await runner.stop() is True
    assert await runner.stop() is False
    assert runner.status().state == BotState.STOPPED


async def test_runner_survives_strategy_errors(tmp_path: Path) -> None:
    runner, strategy = make_runner(tmp_path)

    async def boom(held: set[str], slots: int) -> list[EntrySignal]:
        raise RuntimeError("provider down")

    strategy.find_entries = boom  # type: ignore[method-assign]
    runner.start()
    import asyncio

    await asyncio.sleep(0.15)  # a few failing ticks
    await runner.stop()
    status = runner.status()
    assert status.errors >= 1
    assert status.state == BotState.STOPPED  # loop survived, stop was clean
    assert "provider down" in (status.last_error or "")


# --- endpoints ----------------------------------------------------------------


class StubManager:
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
                open_positions=1,
                closed_trades=4,
                realized_pnl_usd=12.5,
                win_rate_pct=75.0,
            )
        ]

    def trades(self, bot_id: str | None, limit: int) -> list:
        return []

    async def control(self, bot_id: str, action: str) -> BotControlResult:
        return BotControlResult(
            bot_id=bot_id,
            action=action,
            accepted=True,
            state=BotState.RUNNING if action != "stop" else BotState.STOPPED,
            detail="ok. Paper mode: virtual USD only.",
        )


@pytest.fixture()
def bots_client(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_bots] = lambda: StubManager()
    with TestClient(app) as client:
        yield client


def test_list_bots_endpoint(bots_client: TestClient) -> None:
    res = bots_client.get("/api/v1/bots")
    assert res.status_code == 200
    body = res.json()
    assert body[0]["config"]["id"] == "sniper"
    assert body[0]["state"] == "running"
    assert body[0]["realized_pnl_usd"] == 12.5


def test_control_endpoint_real_actions(bots_client: TestClient) -> None:
    res = bots_client.post("/api/v1/bots/sniper/stop")
    assert res.status_code == 200
    assert res.json() == {
        "bot_id": "sniper",
        "action": "stop",
        "accepted": True,
        "state": "stopped",
        "detail": "ok. Paper mode: virtual USD only.",
    }


def test_control_endpoint_rejects_unknown_action(bots_client: TestClient) -> None:
    assert bots_client.post("/api/v1/bots/sniper/explode").status_code == 422
