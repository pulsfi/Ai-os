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
    # Neutralize honest-pricing haircut/cap here — these tests check the
    # exit-trigger logic, not the fill model (that has its own tests).
    return BotRunner(
        config, PricePath(path), BotLedger(tmp_path / "bots.db"),
        exit_slippage_bps=0, max_gain_pct=1_000_000.0,
    )


async def test_reentry_cooldown_blocks_rebuying_same_mint(tmp_path: Path) -> None:
    """After exiting a coin, the bot must not immediately re-buy it."""

    class AlwaysWantsMintX(Strategy):
        name = "always"

        def __init__(self) -> None:  # no clients needed
            pass

        async def find_entries(self, held_mints: set[str], slots: int):
            # Only offers MintX; respects the blocked set the runner passes.
            if "MintX" in held_mints or slots < 1:
                return []
            return [EntrySignal("MintX", "XXX", 1.0, "t")]

        async def current_price(self, mint: str):
            return 0.5  # instant stop-loss so it closes each tick

    config = BotConfig(
        id="cool", name="Cool", strategy="always", description="t",
        interval_s=0.05, usd_per_trade=10, max_open_positions=1,
        take_profit_pct=10, stop_loss_pct=10, max_hold_s=3600,
        exit_slippage_bps=0, max_gain_pct=1_000_000, reentry_cooldown_s=999,
    )
    runner = BotRunner(config, AlwaysWantsMintX(), BotLedger(tmp_path / "b.db"))
    await runner.tick()  # opens MintX
    await runner.tick()  # stop-loss closes it -> cooldown set on MintX
    await runner.tick()  # wants MintX again, but it's cooling -> no re-entry
    trades = runner._ledger.trades("cool", 50)
    assert len(trades) == 1  # exactly one trade, not a re-buy spree


async def test_honest_pricing_caps_moonshot_and_haircuts(tmp_path: Path) -> None:
    """A +400% mark can't be dumped at the mark: gain is capped + haircut."""
    config = BotConfig(
        id="honest", name="Honest", strategy="pricepath", description="t",
        interval_s=0.05, usd_per_trade=100.0, max_open_positions=1,
        take_profit_pct=50.0, stop_loss_pct=90.0, max_hold_s=3600.0,
    )
    # entry 1.0 -> mark 5.0 (+400%). Cap 100%, 2% slippage.
    runner = BotRunner(
        config, PricePath([5.0]), BotLedger(tmp_path / "b.db"),
        exit_slippage_bps=200, max_gain_pct=100.0,
    )
    await runner.tick()  # opens @ 1.0
    await runner.tick()  # +400% mark -> take-profit, but capped
    status = runner.status()
    assert status.closed_trades == 1
    # Capped at +100% then 2% haircut is applied before the cap check, so the
    # credited gain is the +100% cap, not +400%. On $100 that's ~+$100, far
    # below the naive +$400.
    assert status.realized_pnl_usd == pytest.approx(100.0, abs=0.5)
    trade = runner._ledger.trades("honest", 1)[0]
    assert "capped" in (trade.exit_note or "")


async def test_honest_pricing_haircut_on_normal_exit(tmp_path: Path) -> None:
    """A modest win takes a slippage haircut (realistic, slightly less)."""
    config = BotConfig(
        id="hc", name="HC", strategy="pricepath", description="t",
        interval_s=0.05, usd_per_trade=100.0, max_open_positions=1,
        take_profit_pct=10.0, stop_loss_pct=90.0, max_hold_s=3600.0,
    )
    runner = BotRunner(
        config, PricePath([1.20]), BotLedger(tmp_path / "b.db"),
        exit_slippage_bps=200, max_gain_pct=100.0,
    )
    await runner.tick()
    await runner.tick()  # +20% mark -> exit 1.20*0.98=1.176 -> +17.6%
    assert runner.status().realized_pnl_usd == pytest.approx(17.6, abs=0.1)


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


class _WatchMarket:
    """Watchlist with one up-token and one down-token."""

    async def get_watchlist(self):
        from datetime import datetime, timezone

        from modules.market.market_models import TokenMarketData

        def tok(mint, change):
            return TokenMarketData(
                mint=mint, symbol=mint[:4].upper(), price_usd=1.0, change_24h=change,
                volume_24h=None, liquidity_usd=None, market_cap=None, fdv=None,
                sources=["dexscreener"], fetched_at=datetime.now(timezone.utc),
            )

        return [tok("UpMint", 5.0), tok("DownMint", -4.0)]

    async def get_trending(self):
        return await self.get_watchlist()


async def test_flow_scalper_enters_only_confirmed_uptrend() -> None:
    from modules.bots.strategies import FlowScalper

    scalp = FlowScalper(
        StubPumpFun([]), market=_WatchMarket(),  # type: ignore[arg-type]
        helius=StubHelius(activity(buys=8, sells=2, wallets=6)),
    )
    signals = await scalp.find_entries(set(), 5)
    # Only the up-token with confirmed buy pressure; the down-token is skipped.
    assert [s.mint for s in signals] == ["UpMint"]
    assert "buys" in signals[0].note


async def test_flow_scalper_skips_weak_flow() -> None:
    from modules.bots.strategies import FlowScalper

    scalp = FlowScalper(
        StubPumpFun([]), market=_WatchMarket(),  # type: ignore[arg-type]
        helius=StubHelius(activity(buys=3, sells=7, wallets=6)),  # net selling
    )
    assert await scalp.find_entries(set(), 5) == []


class StubRpc:
    """Returns revoked (safe) authorities so scoring can pass on good flow."""

    def __init__(self, mint_auth=None, freeze_auth=None) -> None:
        from models.schemas.solana import TokenAuthorities

        self._auth = TokenAuthorities(mint_authority=mint_auth, freeze_authority=freeze_auth)

    async def get_token_authorities(self, mint: str):
        return self._auth


def fresh_launch_sniper(helius: object, rpc: object | None = None) -> NewLaunchSniper:
    coins = [pump_coin("Fresh1", 10_000)]
    return NewLaunchSniper(
        StubPumpFun(coins), market=None, helius=helius,  # type: ignore[arg-type]
        rpc=rpc or StubRpc(),
    )


async def test_sniper_enters_on_high_confidence() -> None:
    # Revoked authorities + strong broad buying -> score clears the bar.
    sniper = fresh_launch_sniper(StubHelius(activity(buys=8, sells=2, wallets=7)))
    signals = await sniper.find_entries(set(), 3)
    assert len(signals) == 1
    assert "confidence" in signals[0].note


async def test_sniper_skips_sell_pressure() -> None:
    sniper = fresh_launch_sniper(StubHelius(activity(buys=2, sells=6, wallets=5)))
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_hard_rejects_single_wallet() -> None:
    # 100% buys but one wallet = wash/whale -> hard reject regardless of ratio.
    sniper = fresh_launch_sniper(StubHelius(activity(buys=6, sells=0, wallets=1)))
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_hard_rejects_active_mint_authority() -> None:
    # Great flow, but the mint authority is still active -> rug gate fires.
    sniper = fresh_launch_sniper(
        StubHelius(activity(buys=9, sells=1, wallets=10)),
        rpc=StubRpc(mint_auth="SomeAuthorityAddr"),
    )
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_skips_when_flow_lookup_fails() -> None:
    """Can't verify demand -> no entry (reject on missing info)."""
    sniper = fresh_launch_sniper(StubHelius(None))
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_without_flow_stays_out() -> None:
    """No Helius = no demand signal = can't reach the confidence bar -> out."""
    sniper = fresh_launch_sniper(None)
    assert await sniper.find_entries(set(), 3) == []


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
