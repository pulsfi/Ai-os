"""Dynamic Profit Capture engine — pure decision logic + a backtest that
compares tiered scale-out against the old fixed take-profit."""

from modules.bots.profit_capture import (
    DEFAULT_TIERS,
    CaptureState,
    ProfitCaptureConfig,
    ProfitTier,
    evaluate,
)


def cfg(**over) -> ProfitCaptureConfig:
    base = dict(
        enabled=True,
        tiers=[ProfitTier(5, 10), ProfitTier(25, 20), ProfitTier(100, 30), ProfitTier(500, 100)],
        base_trail_drop_pct=15.0, min_trail_drop_pct=4.0,
        decay_after_s=300.0, max_hold_s=1800.0,
    )
    base.update(over)
    return ProfitCaptureConfig(**base)


def run(prices: list[float], *, entry=1.0, held_step=1.0, config=None):
    """Replay a price path, applying actions. Returns (realized_frac_pnl,
    exit_reasons) where pnl is summed as frac*(price/entry-1) per sell."""
    c = config or cfg()
    state = CaptureState()
    peak = entry
    realized = 0.0
    reasons: list[str] = []
    held = 0.0
    for p in prices:
        peak = max(peak, p)
        held += held_step
        for a in evaluate(entry_price=entry, price=p, peak_price=peak,
                          held_s=held, cfg=c, state=state):
            realized += a.sell_frac * (p / entry - 1.0)
            state.remaining_frac -= a.sell_frac
            reasons.append(a.reason)
            if a.kind == "full_close":
                state.remaining_frac = 0.0
        if state.remaining_frac <= 1e-9:
            break
    return realized, reasons, state


def test_partial_sells_fire_at_each_tier() -> None:
    realized, reasons, state = run([1.05, 1.25, 1.30])
    # +5% sold 10%, +25% sold 20% -> two partials, position still partly open.
    assert sum("tier" in r for r in reasons) == 2
    assert 0 < state.remaining_frac < 1.0
    assert realized > 0


def test_top_tier_closes_remaining() -> None:
    realized, reasons, state = run([1.05, 1.25, 2.0, 6.0])
    assert state.remaining_frac == 0.0
    assert any("final" in r for r in reasons)


def test_trailing_stop_only_tightens_never_loosens() -> None:
    c = cfg()
    state = CaptureState()
    # Arm with a tier, then push the peak up and confirm the stop price rises.
    evaluate(entry_price=1.0, price=1.05, peak_price=1.05, held_s=1, cfg=c, state=state)
    evaluate(entry_price=1.0, price=1.5, peak_price=1.5, held_s=2, cfg=c, state=state)
    s1 = state.trail_stop_price
    evaluate(entry_price=1.0, price=3.0, peak_price=3.0, held_s=3, cfg=c, state=state)
    s2 = state.trail_stop_price
    # A pullback must NOT lower the stop.
    evaluate(entry_price=1.0, price=2.5, peak_price=3.0, held_s=4, cfg=c, state=state)
    s3 = state.trail_stop_price
    assert s1 is not None and s2 > s1 and s3 == s2


def test_trailing_stop_tightens_as_gain_grows() -> None:
    from modules.bots.profit_capture import _trail_drop_for

    c = cfg()
    near = _trail_drop_for(c, 20.0, 0.0)
    far = _trail_drop_for(c, 900.0, 0.0)
    assert c.min_trail_drop_pct <= far < near <= c.base_trail_drop_pct


def test_max_hold_force_closes() -> None:
    c = cfg(max_hold_s=3.0)
    _, reasons, state = run([1.05, 1.06, 1.06, 1.06], config=c)
    assert state.remaining_frac == 0.0
    assert any("max-hold" in r for r in reasons)


def test_time_decay_tightens_trailing_stop() -> None:
    from modules.bots.profit_capture import _trail_drop_for

    c = cfg(decay_after_s=100.0)
    fresh = _trail_drop_for(c, 50.0, 50.0)
    aged = _trail_drop_for(c, 50.0, 400.0)
    assert aged < fresh  # older position protected more tightly


def test_disabled_or_flat_entry_is_noop() -> None:
    c = cfg()
    state = CaptureState()
    assert evaluate(entry_price=0.0, price=1.0, peak_price=1.0, held_s=1, cfg=c, state=state) == []


# --- backtest: dynamic capture vs fixed take-profit ------------------------


def fixed_tp_pnl(prices: list[float], entry: float, tp_pct: float, sl_pct: float) -> float:
    """The OLD policy: full close at +tp_pct or -sl_pct, else last price."""
    for p in prices:
        chg = (p / entry - 1.0) * 100.0
        if chg >= tp_pct:
            return tp_pct / 100.0
        if chg <= -sl_pct:
            return -sl_pct / 100.0
    return prices[-1] / entry - 1.0


def capture_pnl(prices: list[float], entry: float, config: ProfitCaptureConfig) -> float:
    realized, _, state = run(prices, entry=entry, config=config)
    # Mark any still-open remainder at the last price (paper close).
    realized += state.remaining_frac * (prices[-1] / entry - 1.0)
    return realized


def test_backtest_capture_beats_fixed_tp_on_a_runner() -> None:
    """On a moonshot that blows through a fixed +40% TP, tiered capture keeps
    a runner and realizes far more."""
    prices = [1.05, 1.25, 1.5, 2.0, 4.0, 8.0, 12.0, 10.0]
    fixed = fixed_tp_pnl(prices, 1.0, tp_pct=40.0, sl_pct=18.0)
    dyn = capture_pnl(prices, 1.0, cfg())
    assert fixed == 0.40  # capped at the fixed TP
    assert dyn > fixed    # capture rode the runner


def test_backtest_capture_protects_on_a_pump_and_dump() -> None:
    """Spikes to +30% then round-trips to 0. Fixed TP (40%) never triggers
    and gives it all back; capture banked partials on the way up."""
    prices = [1.05, 1.30, 1.10, 1.0, 0.9]
    fixed = fixed_tp_pnl(prices, 1.0, tp_pct=40.0, sl_pct=50.0)
    dyn = capture_pnl(prices, 1.0, cfg())
    assert dyn > fixed  # banked the +5% and +25% slices; fixed banked nothing


def test_default_ladder_is_well_formed() -> None:
    total = sum(t.sell_pct for t in DEFAULT_TIERS)
    assert total <= 100.0 + 1e-9  # never sells more than the whole position
    gains = [t.gain_pct for t in DEFAULT_TIERS]
    assert gains == sorted(gains) and gains[0] >= 5 and gains[-1] <= 2000


# --- runner integration: slices in the ledger, same fill model -------------


import pytest as _pytest

from models.schemas.bots import BotConfig, ProfitCaptureSettings, ProfitTierModel
from modules.bots.ledger import BotLedger
from modules.bots.runner import BotRunner
from tests.test_pro_trading import PricePath


def capture_config(**over) -> BotConfig:
    base = dict(
        id="cap", name="Capture", strategy="pricepath", description="t",
        interval_s=0.05, usd_per_trade=100.0, max_open_positions=1,
        take_profit_pct=999.0, stop_loss_pct=90.0, max_hold_s=3600.0,
        profit_capture=ProfitCaptureSettings(
            enabled=True,
            tiers=[ProfitTierModel(gain_pct=5, sell_pct=10),
                   ProfitTierModel(gain_pct=25, sell_pct=20),
                   ProfitTierModel(gain_pct=100, sell_pct=30)],
        ),
    )
    base.update(over)
    return BotConfig(**base)


async def test_runner_books_partial_slices_and_trail_close(tmp_path) -> None:
    """Tier hits become their OWN closed ledger rows (honest stats), the
    open runner shrinks, and the tightening trail closes the remainder —
    all through the same slippage-modelled fill path as every exit."""
    ledger = BotLedger(tmp_path / "cap.db")
    runner = BotRunner(
        capture_config(), PricePath([1.06, 1.30, 1.0]), ledger,
        exit_slippage_bps=0, max_gain_pct=1_000_000.0,
    )
    await runner.tick()  # opens $100 @ 1.0
    await runner.tick()  # +6% -> tier 5 fires: $10 slice realized
    trades = ledger.trades("cap", 10)
    slices = [t for t in trades if t.status == "closed"]
    assert len(slices) == 1 and "tier +5%" in (slices[0].exit_note or "")
    assert slices[0].usd_size == _pytest.approx(10.0)
    open_row = ledger.open_trades("cap")[0]
    assert open_row.usd_size == _pytest.approx(90.0)

    await runner.tick()  # +30% -> tier 25 fires: $20 slice
    open_row = ledger.open_trades("cap")[0]
    assert open_row.usd_size == _pytest.approx(70.0)

    await runner.tick()  # back to 1.0 -> tightening trail closes remainder
    assert ledger.open_trades("cap") == []
    final = next(  # the runner row (original id) closed on the trail
        t for t in ledger.trades("cap", 10) if "profit trail" in (t.exit_note or "")
    )
    assert final.usd_size == _pytest.approx(70.0)
    # Realized total: $10*6% + $20*30% + $70*~0% > 0 — gains were banked.
    total = sum(t.pnl_usd or 0 for t in ledger.trades("cap", 10))
    assert total == _pytest.approx(6.6, abs=0.3)


async def test_runner_capture_mode_keeps_stop_loss_floor(tmp_path) -> None:
    """Risk protections stay immediate in capture mode: a crash hits the
    stop-loss before any capture logic runs."""
    ledger = BotLedger(tmp_path / "sl.db")
    runner = BotRunner(
        capture_config(stop_loss_pct=18.0), PricePath([0.7]), ledger,
        exit_slippage_bps=0, max_gain_pct=1_000_000.0,
    )
    await runner.tick()  # opens
    await runner.tick()  # -30% -> stop-loss (not capture)
    trade = ledger.trades("cap", 1)[0]
    assert trade.status == "closed" and "stop-loss" in (trade.exit_note or "")
