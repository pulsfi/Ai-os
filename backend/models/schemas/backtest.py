"""Backtesting API contracts (capture-replay engine)."""

from pydantic import BaseModel


class BacktestCoverage(BaseModel):
    """How much replayable reality the rolling window holds."""

    samples: int = 0
    sampled_mints: int = 0
    snapshots: int = 0
    evaluated_launches: int = 0
    window_hours: float = 0.0


class VariantResult(BaseModel):
    """One strategy variant's replay over the window."""

    variant: str
    exit_mode: str
    threshold: float
    trades: int = 0
    net_profit_usd: float = 0.0
    profit_factor: float | None = None
    win_rate_pct: float | None = None
    sharpe: float | None = None  # per-trade Sharpe (mean/std of trade PnL)
    max_drawdown_usd: float | None = None
    expectancy_usd: float | None = None
    # Walk-forward verdict: only validated variants may be promoted.
    validated: bool = False


class WalkForwardReport(BaseModel):
    """Chronological train/test folds — the anti-overfitting gate."""

    validated: bool
    exit_mode: str | None = None
    reason: str | None = None
    folds: list[dict] = []


class CandleOut(BaseModel):
    """One OHLC bucket aggregated from recorded samples. `samples` is the
    observation count (no external volume feed exists on the bonding
    curve — reported honestly instead of fabricated volume)."""

    ts: str
    open: float
    high: float
    low: float
    close: float
    samples: int
