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

    def __init__(self, mint_auth=None, freeze_auth=None, holders=None) -> None:
        from models.schemas.solana import TokenAuthorities

        self._auth = TokenAuthorities(mint_authority=mint_auth, freeze_authority=freeze_auth)
        from tests.test_bots import healthy_holders

        self._holders = holders if holders is not None else healthy_holders()

    async def get_token_authorities(self, mint: str):
        return self._auth

    async def get_token_largest_accounts(self, mint: str) -> list[dict]:
        return self._holders


# --- sniper: pump.fun-native CONFIRMATION entry --------------------------
# The sniper no longer reads Helius flow (blind to bonding-curve trades).
# It scores pump.fun-native signals and only buys a launch it has SEEN
# climb — confirmed buy pressure, not a first-sighting guess.


def fresh_launch_sniper(rpc: object | None = None) -> tuple[NewLaunchSniper, StubPumpFun]:
    from tests.test_bots import FlowStubStream

    stub = StubPumpFun([pump_coin("Fresh1", 10_000)])
    sniper = NewLaunchSniper(
        stub, market=None, helius=None,  # type: ignore[arg-type]
        rpc=rpc or StubRpc(), confirm_window_s=0.0,
        stream=FlowStubStream(),  # type: ignore[arg-type]
    )
    return sniper, stub


async def _enter_after_confirm(sniper: NewLaunchSniper, stub: StubPumpFun, second_mcap: float):
    """First sighting only records; a second reading confirms the trend."""
    await sniper.find_entries(set(), 3)
    stub._coins = [pump_coin("Fresh1", second_mcap)]
    return await sniper.find_entries(set(), 3)


async def test_sniper_enters_on_confirmed_climb() -> None:
    # Revoked authorities + a rising market cap -> confirmed buy pressure.
    sniper, stub = fresh_launch_sniper()
    signals = await _enter_after_confirm(sniper, stub, 12_000)
    assert len(signals) == 1
    assert "confidence" in signals[0].note


async def test_sniper_never_buys_on_first_sighting() -> None:
    # Even a strong launch is only recorded on first sight, never bought.
    sniper, _ = fresh_launch_sniper()
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_skips_flat_or_dumping_launch() -> None:
    # Second reading is lower -> no buy pressure -> skip.
    sniper, stub = fresh_launch_sniper()
    assert await _enter_after_confirm(sniper, stub, 8_000) == []


async def test_sniper_hard_rejects_active_mint_authority() -> None:
    # Climbing cap, but the mint authority is still active -> rug gate fires.
    sniper, stub = fresh_launch_sniper(rpc=StubRpc(mint_auth="SomeAuthorityAddr"))
    assert await _enter_after_confirm(sniper, stub, 12_000) == []


async def test_sniper_stays_out_without_market_cap() -> None:
    """No market cap = can't measure demand = stay out (never fabricate)."""
    stub = StubPumpFun([pump_coin("NoCap", None)])
    sniper = NewLaunchSniper(
        stub, market=None, helius=None,  # type: ignore[arg-type]
        rpc=StubRpc(), confirm_window_s=0.0,
    )
    await sniper.find_entries(set(), 3)
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


# --- profitability engine: whale gate, break-even, sizing, expectancy guard ----


async def test_sniper_rejects_whale_concentration() -> None:
    """Confirmed climber, broad buyers — but 5 wallets own half the supply.
    One dump wipes the position, so the holder X-ray must veto the entry."""
    whale_holders = [
        {"uiAmount": 500_000_000.0},  # bonding curve (excluded)
        {"uiAmount": 400_000_000.0},  # whale — 40% of supply
        {"uiAmount": 50_000_000.0},
        {"uiAmount": 30_000_000.0},
        {"uiAmount": 10_000_000.0},
        {"uiAmount": 5_000_000.0},
    ]
    sniper, stub = fresh_launch_sniper(rpc=StubRpc(holders=whale_holders))
    assert await _enter_after_confirm(sniper, stub, 12_000) == []


async def test_break_even_stop_protects_armed_winner(tmp_path: Path) -> None:
    """+12% peak that collapses exits ~flat via break-even, never -18%."""
    config = BotConfig(
        id="bebot", name="BE", strategy="pricepath", description="t",
        interval_s=0.05, usd_per_trade=100.0, max_open_positions=1,
        take_profit_pct=40.0, stop_loss_pct=18.0, max_hold_s=3600.0,
        trail_after_pct=15.0, trail_drop_pct=8.0, break_even_at_pct=10.0,
    )
    runner = BotRunner(
        config, PricePath([1.12, 1.0]), BotLedger(tmp_path / "be.db"),
        exit_slippage_bps=0, max_gain_pct=1_000_000.0,
    )
    await runner.tick()  # opens at 1.0
    await runner.tick()  # 1.12: peak arms break-even (>=10%), still holding
    await runner.tick()  # 1.00: back to entry -> break-even exit, ~0%
    trade = runner._ledger.trades("bebot", 1)[0]
    assert trade.status == "closed"
    assert "break-even" in (trade.exit_note or "")
    assert trade.pnl_pct is not None and abs(trade.pnl_pct) < 1.0


def test_position_size_scales_with_confidence(tmp_path: Path) -> None:
    config = BotConfig(
        id="szbot", name="SZ", strategy="pricepath", description="t",
        interval_s=1, usd_per_trade=50.0, max_open_positions=1,
        take_profit_pct=40.0, stop_loss_pct=18.0, max_hold_s=3600.0,
    )
    ledger = BotLedger(tmp_path / "sz.db")
    runner = BotRunner(config, PricePath([]), ledger)
    assert runner._position_size(None) == 50.0        # unscored -> flat
    assert runner._position_size(55.0) == pytest.approx(30.0)   # gate edge -> 0.6x
    assert runner._position_size(100.0) == pytest.approx(60.0)  # max conviction -> 1.2x
    # A cold streak (5+ recent closed trades, net negative) cuts size 30%.
    for i in range(5):
        tid = ledger.open_trade("szbot", f"M{i}", f"S{i}", 50.0, 1.0)
        ledger.close_trade(tid, 0.9, "stop")
    assert runner._position_size(100.0) == pytest.approx(42.0)  # 60 * 0.7


async def test_risk_governor_halves_size_but_never_stops(tmp_path: Path) -> None:
    """12 straight losers -> profit factor 0 -> the bot KEEPS trading, but
    at half size (never pause trading on poor performance alone)."""
    ledger = BotLedger(tmp_path / "guard.db")
    for i in range(12):
        tid = ledger.open_trade("gbot", f"Mint{i}", f"SY{i}", 50.0, 1.0)
        ledger.close_trade(tid, 0.8, "stop-loss")
    config = BotConfig(
        id="gbot", name="G", strategy="pricepath", description="t",
        interval_s=0.05, usd_per_trade=50.0, max_open_positions=3,
        take_profit_pct=40.0, stop_loss_pct=18.0, max_hold_s=3600.0,
    )
    runner = BotRunner(config, PricePath([]), ledger)
    assert runner._risk_governor() == 0.5
    assert "risk-reduced" in (runner.status().risk_note or "")

    class Eager(Strategy):
        name = "eager"

        def __init__(self) -> None:  # no clients needed
            pass

        async def find_entries(self, held_mints, slots):
            if "FreshMint" in held_mints or slots < 1:
                return []
            return [EntrySignal("FreshMint", "FRS", 1.0, "t")]

        async def current_price(self, mint):
            return 1.0

    runner._strategy = Eager()
    await runner.tick()
    opened = ledger.open_trades("gbot")
    assert len(opened) == 1  # STILL trading
    # size = $50 base x 0.7 cold-streak x 0.5 governor = $17.50
    assert opened[0].usd_size == pytest.approx(17.5)


async def test_sniper_telemetry_records_rejections_and_approvals() -> None:
    """Every rejected launch is logged with the reason; approvals overwrite."""
    sniper, stub = fresh_launch_sniper()
    # First sighting: recorded only -> rejected as unconfirmed momentum.
    assert await sniper.find_entries(set(), 3) == []
    t = sniper.telemetry()
    assert t["signals_detected"] == 1 and t["signals_approved"] == 0
    assert t["reject_reasons"].get("weak_momentum") == 1
    assert t["recent_rejections"][0]["mint"] == "Fresh1"
    # Cap climbs -> the same mint now passes; its rejection is superseded.
    stub._coins = [pump_coin("Fresh1", 12_000)]
    signals = await sniper.find_entries(set(), 3)
    assert [s.mint for s in signals] == ["Fresh1"]
    t = sniper.telemetry()
    assert t["signals_approved"] == 1 and t["rejected_recent"] == 0
    assert t["avg_confidence"] is not None and t["avg_confidence"] > 55


def test_insights_surface_factor_edges(tmp_path: Path) -> None:
    """Winners vs losers per scoring factor, parsed from real trade notes."""
    from modules.bots.manager import BotManager

    ledger = BotLedger(tmp_path / "ins.db")
    t1 = ledger.open_trade("sniper", "W1", "WIN", 50.0, 1.0,
                           "confidence 80/100 [velocity 30/34, buyers 15/18]")
    ledger.close_trade(t1, 1.3, "take-profit")
    t2 = ledger.open_trade("sniper", "L1", "LOSE", 50.0, 1.0,
                           "confidence 56/100 [velocity 20/34, buyers 2/18]")
    ledger.close_trade(t2, 0.7, "stop-loss")

    class _Stub:
        _ledger = ledger
        _FACTOR_RE = BotManager._FACTOR_RE

    result = BotManager.insights(_Stub(), "sniper")
    assert result.closed_analyzed == 2 and result.wins == 1 and result.losses == 1
    buyers = next(f for f in result.factors if f.name == "buyers")
    assert buyers.winners_avg == 15.0 and buyers.losers_avg == 2.0
    assert buyers.edge == 13.0


# --- flow-aware breadth gate + execution threshold ------------------------


async def test_sniper_trades_on_score_when_flow_data_unavailable() -> None:
    """Live incident regression: PumpPortal stopped delivering per-token
    trades and EVERY launch (avg 57.5 conf, some 75+) died on 'no buyer
    flow observed'. When flow is provably unavailable, breadth degrades to
    a scored 0 and the execution threshold decides — strong climbers trade."""
    from tests.test_bots import FlowStubStream

    class NoFlowStream(FlowStubStream):
        def flow(self, mint: str) -> None:
            return None  # stream can't deliver per-token trades

    stub = StubPumpFun([pump_coin("Fresh1", 10_000)])
    sniper = NewLaunchSniper(
        stub, market=None, helius=None,  # type: ignore[arg-type]
        rpc=StubRpc(), confirm_window_s=0.0,
        stream=NoFlowStream(),  # type: ignore[arg-type]
    )
    assert await sniper.find_entries(set(), 3) == []  # first sighting records
    stub._coins = [pump_coin("Fresh1", 12_000)]  # confirmed climber
    signals = await sniper.find_entries(set(), 3)
    assert [s.mint for s in signals] == ["Fresh1"]


async def test_sniper_requires_breadth_while_flow_is_healthy() -> None:
    """When trade data IS flowing, a mint with zero observed trades truly
    has no buyers — the hard reject stays."""
    from tests.test_bots import FlowStubStream

    class HealthyButSilent(FlowStubStream):
        def flow(self, mint: str) -> None:
            return None  # no trades for THIS mint

        def flow_healthy(self, max_age_s: float = 120.0) -> bool:
            return True  # ...while trades flow in general

    stub = StubPumpFun([pump_coin("Fresh1", 10_000)])
    sniper = NewLaunchSniper(
        stub, market=None, helius=None,  # type: ignore[arg-type]
        rpc=StubRpc(), confirm_window_s=0.0,
        stream=HealthyButSilent(),  # type: ignore[arg-type]
    )
    await sniper.find_entries(set(), 3)
    stub._coins = [pump_coin("Fresh1", 12_000)]
    assert await sniper.find_entries(set(), 3) == []
    reasons = sniper.telemetry()["recent_rejections"][0]["reasons"]
    assert any("buyer flow" in r for r in reasons)


async def test_execution_threshold_is_respected() -> None:
    """A raised threshold rejects the same launch as low-confidence — and
    the rejection record carries score AND threshold (never silent)."""
    from tests.test_bots import FlowStubStream

    class NoFlowStream(FlowStubStream):
        def flow(self, mint: str) -> None:
            return None

    stub = StubPumpFun([pump_coin("Fresh1", 10_000)])
    sniper = NewLaunchSniper(
        stub, market=None, helius=None,  # type: ignore[arg-type]
        rpc=StubRpc(), confirm_window_s=0.0, min_confidence=95.0,
        stream=NoFlowStream(),  # type: ignore[arg-type]
    )
    await sniper.find_entries(set(), 3)
    stub._coins = [pump_coin("Fresh1", 12_000)]
    assert await sniper.find_entries(set(), 3) == []  # 95 bar: nothing passes
    rec = sniper.telemetry()["recent_rejections"][0]
    assert rec["threshold"] == 95.0
    assert rec["score"] < 95.0
    assert sniper.telemetry()["reject_reasons"].get("low_confidence") == 1
