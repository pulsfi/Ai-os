"""Dynamic Profit Capture — a configurable, scale-out profit engine.

Replaces the single fixed take-profit with a tiered system: as a position
climbs through configurable gain levels it sells a slice at each, keeps a
runner open for higher tiers, and rides a trailing stop that only ever
TIGHTENS. A stalling position has its effective target decayed over time
and is force-closed at the max hold.

This module is PURE decision logic — no ledger, no I/O, no clock of its
own (the caller passes `held_s`). That keeps it identically usable by the
live paper runner and by the offline backtest/compare harness, and makes
every rule unit-testable. The runner owns state persistence and the actual
(slippage-modelled) fills; risk protections (stop-loss, rug/honeypot,
liquidity pull) remain the runner's immediate-close floor and are NOT
duplicated here.

Sell fractions are expressed as a fraction of the ORIGINAL position, so a
tier list is easy to reason about ("sell 20% at +25%") and the fractions
across all tiers should sum to <= 1.0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ProfitTier:
    """Sell `sell_pct`% of the original position when unrealized gain first
    reaches `gain_pct`%."""

    gain_pct: float
    sell_pct: float


# The spec's default ladder: frequent early de-risking, big runners at the top.
DEFAULT_TIERS: list[ProfitTier] = [
    ProfitTier(5, 10),
    ProfitTier(10, 10),
    ProfitTier(25, 20),
    ProfitTier(50, 10),
    ProfitTier(100, 15),
    ProfitTier(250, 10),
    ProfitTier(500, 10),
    ProfitTier(1000, 5),
    ProfitTier(2000, 10),  # remainder force-closed at the top tier
]


@dataclass
class ProfitCaptureConfig:
    """Everything tunable about the capture engine (all persisted per-bot)."""

    enabled: bool = False
    tiers: list[ProfitTier] = field(default_factory=lambda: list(DEFAULT_TIERS))
    # Trailing stop arms after the first tier is hit. The give-back starts at
    # `base_trail_drop_pct` and tightens toward `min_trail_drop_pct` as the
    # peak gain grows — it never loosens.
    base_trail_drop_pct: float = 15.0
    min_trail_drop_pct: float = 4.0
    # Time decay: after `decay_after_s` with no new tier, the trailing stop
    # tightens further (protect what's there); force-close at `max_hold_s`.
    decay_after_s: float = 300.0
    max_hold_s: float = 1800.0

    def sorted_tiers(self) -> list[ProfitTier]:
        return sorted(self.tiers, key=lambda t: t.gain_pct)


@dataclass
class CaptureState:
    """Mutable per-position state the runner persists across ticks."""

    remaining_frac: float = 1.0
    tiers_hit: list[float] = field(default_factory=list)  # gain_pct of each taken tier
    trail_stop_price: float | None = None  # monotonically rising
    last_tier_at_s: float = 0.0  # held_s when the most recent tier fired


@dataclass(frozen=True)
class CaptureAction:
    """One thing to do this tick. `sell_frac` is a fraction of the ORIGINAL
    position; a full close carries the remaining fraction."""

    kind: Literal["partial_sell", "full_close"]
    sell_frac: float
    reason: str
    tier_pct: float | None = None


_EPS = 1e-9


def _trail_drop_for(cfg: ProfitCaptureConfig, peak_gain_pct: float, held_s: float) -> float:
    """Trailing give-back that tightens as the position runs and as it ages.

    Logarithmic in peak gain so the stop closes in quickly on a moonshot
    (you keep most of a +900% move) but stays loose enough early not to get
    shaken out. Time past `decay_after_s` tightens it further."""
    if peak_gain_pct <= 0:
        return cfg.base_trail_drop_pct
    span = cfg.base_trail_drop_pct - cfg.min_trail_drop_pct
    # 0 at +10%, ~1 by +1000% (log10 scale) -> smooth tightening.
    tighten = min(1.0, math.log10(1 + peak_gain_pct / 10.0) / 2.0)
    drop = cfg.base_trail_drop_pct - span * tighten
    if held_s > cfg.decay_after_s:
        # Age decay: shave up to another 40% of the remaining band as the
        # trade drags on past the decay point (capped so it stays sane).
        overage = min(1.0, (held_s - cfg.decay_after_s) / max(cfg.decay_after_s, 1.0))
        drop -= (drop - cfg.min_trail_drop_pct) * 0.4 * overage
    return max(cfg.min_trail_drop_pct, drop)


def evaluate(
    *,
    entry_price: float,
    price: float,
    peak_price: float,
    held_s: float,
    cfg: ProfitCaptureConfig,
    state: CaptureState,
) -> list[CaptureAction]:
    """Decide this tick's actions for one open position. Mutates `state`
    (tiers_hit, trail_stop_price, last_tier_at_s) so the caller can persist
    it; returns the ordered actions to execute. Never raises on bad input —
    a non-positive entry price yields no actions.

    Precedence: force-close at max hold, then trailing-stop breach, then the
    highest newly-reached profit tier (a spike can clear several at once —
    only the top one fires per tick, the rest fire on subsequent ticks as
    price holds). Stop-loss and rug checks are the runner's job and take
    priority over everything here.
    """
    if entry_price <= 0 or state.remaining_frac <= _EPS:
        return []

    change_pct = (price - entry_price) / entry_price * 100.0
    peak_gain_pct = (max(peak_price, price) - entry_price) / entry_price * 100.0
    tiers = cfg.sorted_tiers()
    armed = bool(state.tiers_hit)

    # 1) Hard time stop.
    if held_s >= cfg.max_hold_s:
        return [CaptureAction("full_close", state.remaining_frac, f"max-hold {int(held_s)}s")]

    # 2) Trailing stop (only after the first tier arms it). Ratchet the stop
    #    price up; it can rise but never fall.
    if armed:
        drop = _trail_drop_for(cfg, peak_gain_pct, held_s)
        candidate = max(peak_price, price) * (1 - drop / 100.0)
        if state.trail_stop_price is None or candidate > state.trail_stop_price:
            state.trail_stop_price = candidate
        if price <= state.trail_stop_price:
            return [
                CaptureAction(
                    "full_close", state.remaining_frac,
                    f"profit trail -{drop:.0f}% (peak +{peak_gain_pct:.0f}%)",
                )
            ]

    # 3) Highest newly-reached tier.
    for tier in reversed(tiers):
        if tier.gain_pct in state.tiers_hit:
            continue
        if change_pct + _EPS >= tier.gain_pct:
            state.tiers_hit.append(tier.gain_pct)
            state.last_tier_at_s = held_s
            is_top = tier is tiers[-1]
            sell = state.remaining_frac if is_top else min(tier.sell_pct / 100.0, state.remaining_frac)
            if is_top or state.remaining_frac - sell <= _EPS:
                return [
                    CaptureAction("full_close", state.remaining_frac,
                                  f"tier +{tier.gain_pct:.0f}% (final)", tier.gain_pct)
                ]
            return [
                CaptureAction("partial_sell", sell,
                              f"tier +{tier.gain_pct:.0f}% sold {tier.sell_pct:.0f}%", tier.gain_pct)
            ]
    return []
