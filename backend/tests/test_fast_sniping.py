"""Fast-sniping tests: launch stream parsing, stream-first entries,
live price marks, and event-driven tick safety. No network anywhere."""

import asyncio
import json
import time
from pathlib import Path

import pytest

from models.schemas.bots import BotConfig
from modules.bots.ledger import BotLedger
from modules.bots.runner import BotRunner
from modules.bots.strategies import EntrySignal, NewLaunchSniper, Strategy
from modules.market.pumpportal import LaunchEvent, LaunchStream
from tests.test_bots import StubPumpFun, pump_coin


# --- stream parsing -----------------------------------------------------------


def test_stream_parses_create_and_trade_events() -> None:
    stream = LaunchStream()
    fired: list[int] = []
    stream.add_listener(lambda: fired.append(1))

    stream._handle(
        json.dumps(
            {
                "txType": "create",
                "mint": "NewMint1",
                "name": "New Coin",
                "symbol": "NEW",
                "marketCapSol": 30.5,
            }
        )
    )
    assert stream.events_seen == 1
    assert fired == [1]
    assert stream.recent(60)[0].mint == "NewMint1"

    # Trades only count for watched mints.
    stream._watched.add("NewMint1")
    stream._handle(json.dumps({"txType": "buy", "mint": "NewMint1", "marketCapSol": 45.0}))
    assert stream.latest_mcap_sol("NewMint1") == 45.0

    # Garbage never raises.
    stream._handle("not json")
    stream._handle(json.dumps(["not", "a", "dict"]))


def test_stream_recent_expires_old_events() -> None:
    stream = LaunchStream()
    stream._events.append(
        LaunchEvent(mint="Old", name="", symbol="", mcap_sol=1.0,
                    received_at=time.monotonic() - 500)
    )
    stream._events.append(LaunchEvent(mint="Fresh", name="", symbol="", mcap_sol=1.0))
    assert [e.mint for e in stream.recent(60)] == ["Fresh"]


def test_stream_auto_watches_new_launches() -> None:
    """Every create is auto-subscribed for its candidacy window, so its
    trades update the live mark WITHOUT a manual watch — that moving mark
    is the sniper's velocity source."""
    stream = LaunchStream(watch_window_s=300.0)
    stream._handle(json.dumps({"txType": "create", "mint": "AutoMint", "marketCapSol": 28.0}))
    assert "AutoMint" in stream._auto
    # A trade lands for the candidate (never manually watched):
    stream._handle(json.dumps({"txType": "buy", "mint": "AutoMint", "marketCapSol": 40.0}))
    assert stream.latest_mcap_sol("AutoMint") == 40.0


def test_stream_auto_watch_expires_but_held_mints_survive() -> None:
    stream = LaunchStream(watch_window_s=300.0)
    now = time.monotonic()
    stream._auto = {"Expired": now - 400, "HeldOne": now - 400, "Alive": now}
    stream._watched = {"HeldOne"}
    stream._trade_mcap = {"Expired": (1.0, now), "HeldOne": (2.0, now), "Alive": (3.0, now)}
    stream._prune_auto()
    assert set(stream._auto) == {"Alive"}
    assert "Expired" not in stream._trade_mcap      # candidate gone
    assert stream._trade_mcap["HeldOne"] == (2.0, now)  # position mark kept


def test_stream_tracks_demand_breadth_per_candidate() -> None:
    """The trade feed carries the buyer's wallet: distinct-buyer counting is
    the free anti-bundle signal (no API calls)."""
    stream = LaunchStream()
    stream._handle(json.dumps({"txType": "create", "mint": "M1", "marketCapSol": 28.0}))
    assert stream.flow("M1") is None  # no trades seen yet
    for wallet in ("walletA", "walletB", "walletA", "walletC"):
        stream._handle(json.dumps(
            {"txType": "buy", "mint": "M1", "marketCapSol": 30.0, "traderPublicKey": wallet}
        ))
    stream._handle(json.dumps(
        {"txType": "sell", "mint": "M1", "marketCapSol": 29.0, "traderPublicKey": "walletD"}
    ))
    assert stream.flow("M1") == (3, 4, 1)  # 3 distinct buyers, 4 buys, 1 sell
    # Untracked mints accumulate nothing.
    stream._handle(json.dumps({"txType": "buy", "mint": "Rando", "marketCapSol": 9.0}))
    assert stream.flow("Rando") is None


def test_stream_candidate_trades_wake_the_sniper() -> None:
    """A candidate's trade fires listeners (velocity changed -> tick NOW)."""
    stream = LaunchStream()
    fired: list[int] = []
    stream.add_listener(lambda: fired.append(1))
    stream._handle(json.dumps({"txType": "create", "mint": "M1", "marketCapSol": 28.0}))
    assert len(fired) == 1  # the launch itself
    stream._handle(json.dumps({"txType": "buy", "mint": "M1", "marketCapSol": 30.0}))
    assert len(fired) == 2  # the candidate's trade
    # Trades for mints we don't track do NOT wake anyone.
    stream._handle(json.dumps({"txType": "buy", "mint": "Other", "marketCapSol": 9.9}))
    assert len(fired) == 2


# --- stream-first sniper -------------------------------------------------------


class FakeStream:
    """Duck-typed LaunchStream for strategy tests (healthy breadth default —
    the sniper hard-rejects any entry without verified breadth)."""

    def __init__(self, events: list[LaunchEvent], trade_mcap: dict[str, float] | None = None,
                 flow: tuple[int, int, int] | None = (8, 20, 3)):
        self._events = events
        self._trade = trade_mcap or {}
        self._flow_default = flow
        self.watched: list[str] = []
        self.unwatched: list[str] = []

    def recent(self, max_age_s: float) -> list[LaunchEvent]:
        return self._events

    def latest_mcap_sol(self, mint: str, max_age_s: float = 20.0) -> float | None:
        return self._trade.get(mint)

    def flow(self, mint: str) -> tuple[int, int, int] | None:
        return self._flow_default

    async def watch(self, mint: str) -> None:
        self.watched.append(mint)

    async def unwatch(self, mint: str) -> None:
        self.unwatched.append(mint)


class FakeMarket:
    """Watchlist with SOL at $200 (makes mcapSol -> USD math easy)."""

    async def get_watchlist(self):
        from datetime import datetime, timezone

        from modules.market.market_models import TokenMarketData

        return [
            TokenMarketData(
                mint="So11111111111111111111111111111111111111112",
                symbol="SOL",
                price_usd=200.0,
                change_24h=None,
                volume_24h=None,
                liquidity_usd=None,
                market_cap=None,
                fdv=None,
                sources=["test"],
                fetched_at=datetime.now(timezone.utc),
            )
        ]


class _GoodHelius:
    """Strong, broad buy-pressure so the confidence score clears the bar."""

    is_configured = True

    async def get_token_activity(self, mint: str, limit: int = 30):
        from modules.market.helius import TokenActivity

        return TokenActivity(
            mint=mint, sampled_txs=20, swaps=20, buys=17, sells=3,
            buy_ratio_pct=85.0, unique_wallets=12,
        )


class _OkRpc:
    async def get_token_authorities(self, mint: str):
        from models.schemas.solana import TokenAuthorities

        return TokenAuthorities(mint_authority=None, freeze_authority=None)


async def test_sniper_prefers_stream_and_watches_entries() -> None:
    # 100 SOL mcap * $200 = $20,000 -> inside the band. Confirmation entry:
    # the first sighting only records; entry comes once the cap has climbed.
    stream = FakeStream([LaunchEvent(mint="StreamMint", name="S", symbol="STRM", mcap_sol=100.0)])
    sniper = NewLaunchSniper(
        StubPumpFun([]), market=FakeMarket(), helius=_GoodHelius(), stream=stream,  # type: ignore[arg-type]
        rpc=_OkRpc(), confirm_window_s=0.0,
    )
    assert await sniper.find_entries(set(), 3) == []  # first sighting -> record only
    # Cap climbs 100 -> 110 SOL ($22,000): confirmed buy pressure.
    stream._events = [LaunchEvent(mint="StreamMint", name="S", symbol="STRM", mcap_sol=110.0)]
    signals = await sniper.find_entries(set(), 3)
    assert len(signals) == 1
    assert signals[0].mint == "StreamMint"
    assert "stream-detected" in signals[0].note
    assert signals[0].price_usd == pytest.approx(22_000 / 1_000_000_000)
    assert stream.watched == ["StreamMint"]  # live marks subscribed


async def test_sniper_stream_band_filter_applies() -> None:
    # 1 SOL mcap = $200 -> below the $6k floor; must be skipped.
    events = [LaunchEvent(mint="Tiny", name="", symbol="T", mcap_sol=1.0)]
    sniper = NewLaunchSniper(
        StubPumpFun([]), market=FakeMarket(), helius=None, stream=FakeStream(events),  # type: ignore[arg-type]
    )
    assert await sniper.find_entries(set(), 3) == []


async def test_sniper_velocity_reads_live_trade_marks() -> None:
    """Regression for the zero-trades defect: the create event's mcap is a
    frozen snapshot, so velocity MUST come from the live trade mark that
    the auto-watch keeps updated — otherwise every launch reads flat and
    is rejected forever."""
    event = LaunchEvent(mint="LiveMint", name="L", symbol="LVE", mcap_sol=100.0)
    stream = FakeStream([event], trade_mcap={"LiveMint": 100.0})
    sniper = NewLaunchSniper(
        StubPumpFun([]), market=FakeMarket(), stream=stream,  # type: ignore[arg-type]
        rpc=_OkRpc(), confirm_window_s=0.0,
    )
    assert await sniper.find_entries(set(), 3) == []  # first reading recorded
    # The mark moves 100 -> 110 SOL while the create snapshot stays frozen:
    stream._trade["LiveMint"] = 110.0
    signals = await sniper.find_entries(set(), 3)
    assert [s.mint for s in signals] == ["LiveMint"]
    assert signals[0].price_usd == pytest.approx(22_000 / 1_000_000_000)


async def test_sniper_rest_fallback_still_works_with_stream() -> None:
    """Stream empty (e.g. disconnected) -> the REST sweep still enters once
    the launch confirms it's climbing."""
    stub = StubPumpFun([pump_coin("RestMint", 10_000)])
    sniper = NewLaunchSniper(
        stub, market=FakeMarket(), helius=_GoodHelius(),  # type: ignore[arg-type]
        stream=FakeStream([]), rpc=_OkRpc(), confirm_window_s=0.0,
    )
    assert await sniper.find_entries(set(), 3) == []  # first sighting -> record only
    stub._coins = [pump_coin("RestMint", 11_500)]     # cap climbs -> confirmed
    signals = await sniper.find_entries(set(), 3)
    assert [s.mint for s in signals] == ["RestMint"]


async def test_current_price_uses_live_trade_mark_first() -> None:
    stream = FakeStream([], trade_mcap={"HeldMint": 150.0})
    sniper = NewLaunchSniper(
        StubPumpFun([]), market=FakeMarket(), helius=None, stream=stream,  # type: ignore[arg-type]
    )
    # 150 SOL * $200 / 1B supply
    assert await sniper.current_price("HeldMint") == pytest.approx(
        150.0 * 200 / 1_000_000_000
    )


async def test_close_hook_unwatches_mint(tmp_path: Path) -> None:
    stream = FakeStream([])

    class OneShot(Strategy):
        name = "oneshot"

        def __init__(self) -> None:
            self._stream = stream
            self.entered = False

        async def find_entries(self, held, slots):
            if self.entered:
                return []
            self.entered = True
            return [EntrySignal("MintZ", "ZZZ", 1.0, "t")]

        async def current_price(self, mint):
            return 0.5  # instant stop-loss

        async def on_position_closed(self, mint: str) -> None:
            await stream.unwatch(mint)

    config = BotConfig(
        id="hookbot", name="Hook", strategy="oneshot", description="t",
        interval_s=0.05, usd_per_trade=10, max_open_positions=1,
        take_profit_pct=10, stop_loss_pct=10, max_hold_s=3600,
    )
    runner = BotRunner(config, OneShot(), BotLedger(tmp_path / "b.db"))
    await runner.tick()  # open
    await runner.tick()  # stop-loss close -> schedules the hook
    await asyncio.sleep(0)  # let the hook task run
    assert stream.unwatched == ["MintZ"]


# --- event-driven tick safety ---------------------------------------------------


async def test_request_tick_burst_never_double_enters(tmp_path: Path) -> None:
    class SlowEntry(Strategy):
        name = "slow"

        def __init__(self) -> None:
            self.calls = 0

        async def find_entries(self, held, slots):
            self.calls += 1
            await asyncio.sleep(0.02)  # widen the race window
            if held or slots < 1:
                return []
            return [EntrySignal("MintY", "YYY", 1.0, "t")]

        async def current_price(self, mint):
            return 1.0

    config = BotConfig(
        id="burstbot", name="Burst", strategy="slow", description="t",
        interval_s=999, usd_per_trade=10, max_open_positions=1,
        take_profit_pct=10, stop_loss_pct=10, max_hold_s=3600,
    )
    ledger = BotLedger(tmp_path / "b.db")
    runner = BotRunner(config, SlowEntry(), ledger)
    runner.start()
    for _ in range(5):  # burst of launch events
        runner.request_tick()
    await asyncio.sleep(0.3)
    await runner.stop()
    assert len(ledger.trades("burstbot", 50)) == 1  # exactly one position
