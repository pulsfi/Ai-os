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


class _GoodHelius:
    is_configured = True

    async def get_token_activity(self, mint: str, limit: int = 30):
        from modules.market.helius import TokenActivity

        return TokenActivity(
            mint=mint, sampled_txs=20, swaps=20, buys=17, sells=3,
            buy_ratio_pct=85.0, unique_wallets=12,
        )


def healthy_holders() -> list[dict]:
    """Bonding curve holds ~79%, then small real holders (top5 ≈ 5%)."""
    return [{"uiAmount": 793_000_000.0}] + [{"uiAmount": 10_000_000.0}] * 8


class _OkRpc:
    async def get_token_authorities(self, mint: str):
        from models.schemas.solana import TokenAuthorities

        return TokenAuthorities(mint_authority=None, freeze_authority=None)

    async def get_token_largest_accounts(self, mint: str) -> list[dict]:
        return healthy_holders()


class FlowStubStream:
    """Minimal stream stub: no live events/marks, but healthy demand breadth
    (the sniper now refuses ANY entry without verified breadth)."""

    def recent(self, max_age_s: float) -> list:
        return []

    def latest_mcap_sol(self, mint: str, max_age_s: float = 20.0) -> None:
        return None

    def flow(self, mint: str) -> tuple[int, int, int]:
        return (8, 20, 3)  # broad, buy-heavy

    async def watch(self, mint: str) -> None:
        pass

    async def unwatch(self, mint: str) -> None:
        pass


async def test_sniper_filters_and_prices() -> None:
    def coins(bump: float = 0) -> list:
        return [
            pump_coin("Fresh1", 10_000 + bump),               # good, climbing
            pump_coin("TooOld", 10_000 + bump, age_s=600),    # too old
            pump_coin("TooSmall", 2_000),                     # below mcap floor
            pump_coin("NoReplies", 10_000 + bump, replies=0), # fine: replies score, not gate
            pump_coin("Done", 10_000 + bump, complete=True),  # graduated
            pump_coin("Fresh2", 20_000 + bump),               # good, climbing
        ]

    stub = StubPumpFun(coins())
    sniper = NewLaunchSniper(
        stub, market=None,  # type: ignore[arg-type]
        helius=_GoodHelius(), rpc=_OkRpc(), confirm_window_s=0.0,
        stream=FlowStubStream(),  # type: ignore[arg-type]
    )
    # First pass records sightings — nothing is bought on sight (confirmation).
    assert await sniper.find_entries(held_mints=set(), slots=5) == []
    # Caps climb -> confirmed buy pressure -> the climbing ones enter
    # (zero replies is a scored factor, not a hard gate).
    stub._coins = coins(bump=1_500)
    signals = await sniper.find_entries(held_mints=set(), slots=5)
    assert [s.mint for s in signals] == ["Fresh1", "NoReplies", "Fresh2"]
    # price = mcap / 1B fixed supply
    assert signals[0].price_usd == pytest.approx(11_500 / 1_000_000_000)
    # held mints are excluded (caps still climbing)
    stub._coins = coins(bump=3_000)
    signals = await sniper.find_entries(held_mints={"Fresh1"}, slots=5)
    assert [s.mint for s in signals] == ["NoReplies", "Fresh2"]


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

    def update_config(self, bot_id, update):
        s = self.statuses()[0]
        return s.model_copy(update={"config": s.config.model_copy(
            update=update.model_dump(exclude_none=True))})


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


def test_update_config_endpoint(bots_client: TestClient) -> None:
    res = bots_client.patch(
        "/api/v1/bots/sniper/config", json={"take_profit_pct": 25, "usd_per_trade": 20}
    )
    assert res.status_code == 200
    assert res.json()["config"]["take_profit_pct"] == 25
    assert res.json()["config"]["usd_per_trade"] == 20


def test_update_config_validates(bots_client: TestClient) -> None:
    # take_profit must be > 0
    assert bots_client.patch(
        "/api/v1/bots/sniper/config", json={"take_profit_pct": 0}
    ).status_code == 422


def test_config_override_persists_and_reloads(tmp_path: Path, settings: Settings) -> None:
    """update_config writes overrides; a fresh manager loads them."""
    from config import Settings as S
    from models.schemas.bots import BotConfigUpdate
    from modules.bots.manager import BotManager

    s = S(
        _env_file=None,
        bots_db_path=str(tmp_path / "b.db"),
        bots_overrides_path=str(tmp_path / "ov.json"),
        pumpportal_enabled=False,
        log_level="WARNING",
    )
    mgr = BotManager(s)
    status = mgr.update_config("sniper", BotConfigUpdate(take_profit_pct=33.0))
    assert status.config.take_profit_pct == 33.0
    assert (tmp_path / "ov.json").is_file()
    # A brand-new manager picks up the saved override.
    mgr2 = BotManager(s)
    assert mgr2.statuses()  # built ok
    sniper = next(b for b in mgr2.statuses() if b.config.id == "sniper")
    assert sniper.config.take_profit_pct == 33.0
