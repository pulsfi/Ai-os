"""Milestone 9 tests: trailing stops, flow-gated sniper, report scheduler."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from config import Settings
from models.schemas.bots import BotConfig
from modules.bots.ledger import BotLedger
from modules.bots.runner import BotRunner
from modules.bots.strategies import EntrySignal, NewLaunchSniper, Strategy
from modules.market.helius import TokenActivity
from modules.vault import VaultService
from modules.vault.report_scheduler import seconds_until_hour_utc
from tests.test_bots import StubPumpFun, pump_coin


# --- trailing stop -----------------------------------------------------------


class PricePath(Strategy):
    """Enters once at 1.0, then replays a scripted price path."""

    name = "pricepath"

    def __init__(self, path: list[float]) -> None:
        self._path = list(path)
        self._entered = False

    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        if self._entered or slots < 1:
            return []
        self._entered = True
        return [EntrySignal("MintX", "XXX", 1.0, "scripted")]

    async def current_price(self, mint: str) -> float | None:
        return self._path.pop(0) if self._path else None


def trailing_runner(tmp_path: Path, path: list[float]) -> BotRunner:
    config = BotConfig(
        id="trailbot",
        name="Trail Bot",
        strategy="pricepath",
        description="t",
        interval_s=0.05,
        usd_per_trade=100.0,
        max_open_positions=1,
        take_profit_pct=50.0,  # far away — the trail must fire first
        stop_loss_pct=30.0,
        max_hold_s=3600.0,
        trail_after_pct=10.0,
        trail_drop_pct=5.0,
    )
    return BotRunner(config, PricePath(path), BotLedger(tmp_path / "bots.db"))


async def test_trailing_stop_locks_in_profit(tmp_path: Path) -> None:
    # entry 1.0 -> peaks 1.20 (armed) -> falls to 1.10 (>5% off peak) -> close
    runner = trailing_runner(tmp_path, [1.20, 1.10])
    await runner.tick()  # opens
    await runner.tick()  # peak 1.20, armed
    await runner.tick()  # 1.10 is 8.3% below peak -> trailing stop
    status = runner.status()
    assert status.closed_trades == 1
    assert status.realized_pnl_usd == pytest.approx(10.0, abs=0.01)  # locked +10%
    trade = runner._ledger.trades("trailbot", 1)[0]
    assert "trailing-stop" in (trade.exit_note or "")


async def test_trailing_stop_not_armed_below_threshold(tmp_path: Path) -> None:
    # peaks only +8% (< trail_after 10%) then dips — position must stay open
    runner = trailing_runner(tmp_path, [1.08, 1.02, 1.02])
    await runner.tick()
    await runner.tick()
    await runner.tick()
    assert runner.status().open_positions == 1


# --- flow-gated sniper ---------------------------------------------------------


class StubHelius:
    def __init__(self, activity: TokenActivity | None) -> None:
        self._activity = activity
        self.is_configured = True

    async def get_token_activity(self, mint: str, limit: int = 30) -> TokenActivity:
        if self._activity is None:
            from core.exceptions import ExternalServiceError

            raise ExternalServiceError("helius down")
        return self._activity


def activity(buys: int, sells: int, wallets: int) -> TokenActivity:
    total = buys + sells
    return TokenActivity(
        mint="m",
        sampled_txs=total,
        swaps=total,
        buys=buys,
        sells=sells,
        buy_ratio_pct=round(buys / total * 100, 1) if total else None,
        unique_wallets=wallets,
    )


def fresh_launch_sniper(helius: object) -> NewLaunchSniper:
    coins = [pump_coin("Fresh1", 10_000)]
    return NewLaunchSniper(StubPumpFun(coins), market=None, helius=helius)  # type: ignore[arg-type]


async def test_sniper_enters_on_confirmed_flow() -> None:
    sniper = fresh_launch_sniper(StubHelius(activity(buys=6, sells=2, wallets=5)))
    signals = await sniper.find_entries(set(), 3)
    assert len(signals) == 1
    assert "flow 75.0% buys" in signals[0].note


async def test_sniper_skips_sell_pressure() -> None:
    sniper = fresh_launch_sniper(StubHelius(activity(buys=2, sells=6, wallets=5)))
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_skips_too_few_wallets() -> None:
    sniper = fresh_launch_sniper(StubHelius(activity(buys=6, sells=0, wallets=1)))
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_skips_when_flow_lookup_fails() -> None:
    """Conservative: can't verify flow -> no entry."""
    sniper = fresh_launch_sniper(StubHelius(None))
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_without_helius_still_trades() -> None:
    """No key = gate off (stated in the note), basic filters still apply."""
    sniper = fresh_launch_sniper(None)
    signals = await sniper.find_entries(set(), 3)
    assert len(signals) == 1
    assert "flow gate off" in signals[0].note


# --- report scheduler -----------------------------------------------------------


def test_seconds_until_hour_utc() -> None:
    now = datetime(2026, 7, 5, 18, 30, tzinfo=timezone.utc)
    assert seconds_until_hour_utc(20, now) == pytest.approx(1.5 * 3600)
    # Already past today's slot -> tomorrow
    assert seconds_until_hour_utc(18, now) == pytest.approx(23.5 * 3600)
    assert seconds_until_hour_utc(18, now.replace(minute=0)) == pytest.approx(24 * 3600)


def test_scheduler_write_now_appends(tmp_path: Path) -> None:
    from modules.vault.report_scheduler import DailyReportScheduler

    class StubBots:
        def statuses(self) -> list:
            return []

        def performance(self) -> list:
            return []

    vault = VaultService(Settings(_env_file=None, vault_path=tmp_path))
    sched = DailyReportScheduler(StubBots(), vault, hour_utc=20)  # type: ignore[arg-type]
    rel = sched.write_now()
    assert sched.runs == 1
    assert "Bot Fleet Report (auto)" in (tmp_path / rel).read_text(encoding="utf-8")
