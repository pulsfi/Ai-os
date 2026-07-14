"""BacktestEngine — strategy tester, ranking, and walk-forward validation.

Replays recorded launches: for each snapshot whose score clears a variant's
threshold, simulate an entry at the recorded price and walk the recorded
price path applying the variant's exit policy — either the legacy fixed
TP/SL/trail or the Dynamic Profit Capture engine (the SAME pure module the
live runner executes, which is the whole point of capture-replay: paper,
live, and backtest share one brain).

Fills use the live fill model: slippage haircut on every exit and a
per-trade gain cap. Metrics per variant: net profit, profit factor, win
rate, per-trade Sharpe, max drawdown, expectancy.

Walk-forward: the recorded window is split chronologically into folds; the
threshold is chosen on the train side and scored on the unseen test side.
A variant is VALIDATED only when its out-of-sample record holds up —
in-sample-only winners stay flagged unvalidated and should not be promoted.
"""

import math
from dataclasses import dataclass

from modules.backtest.recorder import MarketRecorder
from modules.bots.profit_capture import (
    CaptureState,
    ProfitCaptureConfig,
    evaluate as capture_evaluate,
)

# The sniper's live fill model (mirrors BotConfig defaults).
SLIPPAGE_BPS = 300
MAX_GAIN_PCT = 60.0
USD_PER_TRADE = 50.0


@dataclass(frozen=True)
class SimTrade:
    mint: str
    pnl_usd: float
    pnl_pct: float
    exit_reason: str


def _fill(entry: float, mark: float) -> float:
    """Slippage haircut + gain cap — identical shape to the runner's."""
    exit_price = mark * (1 - SLIPPAGE_BPS / 10_000)
    cap = entry * (1 + MAX_GAIN_PCT / 100)
    return min(exit_price, cap)


def _simulate_fixed(entry: float, path: list[tuple[float, float]], t0: float) -> tuple[float, str]:
    """Legacy exits: TP +40, SL -18, trail 15/8, stall 90s/3%, hold 900s."""
    peak = entry
    for ts, p in path:
        held = ts - t0
        peak = max(peak, p)
        chg = (p / entry - 1) * 100
        peak_gain = (peak / entry - 1) * 100
        if chg >= 40:
            return _fill(entry, p), "take-profit"
        if peak_gain >= 15 and p <= peak * 0.92:
            return _fill(entry, p), "trailing-stop"
        if peak_gain >= 10 and chg <= 0.5:
            return _fill(entry, p), "break-even"
        if held >= 90 and peak_gain < 3 and chg < 3:
            return _fill(entry, p), "stall-exit"
        if chg <= -18:
            return _fill(entry, p), "stop-loss"
        if held >= 900:
            return _fill(entry, p), "max-hold"
    return _fill(entry, path[-1][1]), "data-end"


def _simulate_capture(entry: float, path: list[tuple[float, float]], t0: float) -> tuple[float, str]:
    """Dynamic Profit Capture exits + the same risk floor (SL/stall)."""
    cfg = ProfitCaptureConfig(enabled=True, max_hold_s=900.0)
    state = CaptureState()
    peak = entry
    realized_usd_per_unit = 0.0  # summed exit value of sold fractions
    for ts, p in path:
        held = ts - t0
        peak = max(peak, p)
        chg = (p / entry - 1) * 100
        peak_gain = (peak / entry - 1) * 100
        if chg <= -18:
            realized_usd_per_unit += state.remaining_frac * _fill(entry, p)
            return realized_usd_per_unit, "stop-loss"
        if held >= 90 and peak_gain < 3 and chg < 3 and not state.tiers_hit:
            realized_usd_per_unit += state.remaining_frac * _fill(entry, p)
            return realized_usd_per_unit, "stall-exit"
        for action in capture_evaluate(
            entry_price=entry, price=p, peak_price=peak,
            held_s=held, cfg=cfg, state=state,
        ):
            realized_usd_per_unit += action.sell_frac * _fill(entry, p)
            state.remaining_frac = max(0.0, state.remaining_frac - action.sell_frac)
            if action.kind == "full_close":
                state.remaining_frac = 0.0
                return realized_usd_per_unit, f"capture {action.reason}"
    realized_usd_per_unit += state.remaining_frac * _fill(entry, path[-1][1])
    return realized_usd_per_unit, "data-end"


class BacktestEngine:
    """Runs strategy variants over the recorder's window."""

    def __init__(self, recorder: MarketRecorder) -> None:
        self._recorder = recorder

    def _trades_for(
        self, launches: list[dict], threshold: float, exit_mode: str
    ) -> list[SimTrade]:
        trades: list[SimTrade] = []
        for launch in launches:
            if launch["score"] < threshold or not launch["mcap_usd"]:
                continue
            entry = launch["mcap_usd"] / 1e9  # pump fixed 1B supply
            path = self._recorder.path(launch["mint"], launch["ts"])
            if len(path) < 2:
                continue  # nothing recorded after entry — can't replay honestly
            if exit_mode == "capture":
                exit_value, reason = _simulate_capture(entry, path, launch["ts"])
                pnl_pct = (exit_value / entry - 1) * 100
            else:
                exit_price, reason = _simulate_fixed(entry, path, launch["ts"])
                pnl_pct = (exit_price / entry - 1) * 100
            trades.append(SimTrade(
                mint=launch["mint"],
                pnl_usd=round(USD_PER_TRADE * pnl_pct / 100, 4),
                pnl_pct=round(pnl_pct, 2),
                exit_reason=reason,
            ))
        return trades

    @staticmethod
    def metrics(trades: list[SimTrade]) -> dict:
        n = len(trades)
        if n == 0:
            return {"trades": 0, "net_profit_usd": 0.0, "profit_factor": None,
                    "win_rate_pct": None, "sharpe": None,
                    "max_drawdown_usd": None, "expectancy_usd": None}
        pnls = [t.pnl_usd for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [-p for p in pnls if p < 0]
        equity = peak = dd = 0.0
        for p in pnls:
            equity += p
            peak = max(peak, equity)
            dd = max(dd, peak - equity)
        mean = sum(pnls) / n
        std = math.sqrt(sum((p - mean) ** 2 for p in pnls) / (n - 1)) if n > 1 else 0.0
        return {
            "trades": n,
            "net_profit_usd": round(sum(pnls), 2),
            "profit_factor": round(sum(wins) / sum(losses), 2) if losses else None,
            "win_rate_pct": round(len(wins) / n * 100, 1),
            "sharpe": round(mean / std, 2) if std > 0 else None,  # per-trade
            "max_drawdown_usd": round(dd, 2),
            "expectancy_usd": round(mean, 2),
        }

    # -- strategy tester + ranking ------------------------------------------

    def rank(
        self,
        window_days: float = 5.0,
        thresholds: tuple[float, ...] = (50, 55, 60, 65),
        exit_modes: tuple[str, ...] = ("fixed", "capture"),
    ) -> list[dict]:
        """Grid of variants over the full window, ranked by expectancy, each
        carrying its walk-forward validation verdict."""
        launches = self._recorder.launches(window_days)
        results = []
        for mode in exit_modes:
            wf = self.walk_forward(window_days=window_days, exit_mode=mode)
            for th in thresholds:
                m = self.metrics(self._trades_for(launches, th, mode))
                results.append({
                    "variant": f"{mode}@{th:.0f}",
                    "exit_mode": mode,
                    "threshold": th,
                    **m,
                    "validated": bool(wf.get("validated"))
                    and m["trades"] >= 10
                    and (m["expectancy_usd"] or 0) > 0,
                })
        results.sort(key=lambda r: (r["expectancy_usd"] is not None,
                                    r["expectancy_usd"] or -1e9), reverse=True)
        return results

    # -- walk-forward validation ----------------------------------------------

    def walk_forward(
        self,
        window_days: float = 5.0,
        exit_mode: str = "capture",
        folds: int = 3,
        thresholds: tuple[float, ...] = (50, 55, 60, 65),
    ) -> dict:
        """Chronological k-fold: choose the threshold on the train side,
        score it on the unseen test side. Validated only when out-of-sample
        expectancy stays positive — the anti-overfitting gate that decides
        whether a variant may be promoted."""
        launches = self._recorder.launches(window_days)
        if len(launches) < folds * 8:
            return {"validated": False, "reason":
                    f"insufficient data: {len(launches)} launches recorded, "
                    f"need >= {folds * 8}", "folds": []}
        size = len(launches) // folds
        fold_reports = []
        oos_expectancies = []
        for i in range(1, folds):
            train = launches[: i * size]
            test = launches[i * size: (i + 1) * size]
            best_th, best_exp = None, -1e18
            for th in thresholds:
                m = self.metrics(self._trades_for(train, th, exit_mode))
                exp = m["expectancy_usd"] if m["expectancy_usd"] is not None else -1e18
                if m["trades"] >= 5 and exp > best_exp:
                    best_th, best_exp = th, exp
            if best_th is None:
                fold_reports.append({"fold": i, "reason": "no tradable threshold in train"})
                continue
            oos = self.metrics(self._trades_for(test, best_th, exit_mode))
            oos_expectancies.append(oos["expectancy_usd"] or 0.0)
            fold_reports.append({
                "fold": i, "train_n": len(train), "test_n": len(test),
                "chosen_threshold": best_th,
                "in_sample_expectancy": round(best_exp, 2),
                "out_of_sample": oos,
            })
        validated = (
            len(oos_expectancies) == folds - 1
            and all(e > 0 for e in oos_expectancies)
        )
        return {"validated": validated, "exit_mode": exit_mode,
                "reason": None if validated else "out-of-sample expectancy not consistently positive",
                "folds": fold_reports}
