"""Backtesting endpoints — capture-replay over the recorded rolling window.

The recorder accumulates real observed launches + price paths as the
sniper runs; these endpoints replay that reality against strategy
variants. Cold start is reported honestly via /coverage — a backtest with
insufficient data says so instead of inventing results.
"""

from fastapi import APIRouter, Query

from core.dependencies import BacktestDep
from models.schemas.backtest import (
    BacktestCoverage,
    CandleOut,
    VariantResult,
    WalkForwardReport,
)

router = APIRouter()


@router.get("/coverage", response_model=BacktestCoverage)
async def coverage(engine: BacktestDep) -> BacktestCoverage:
    """How much replayable history the rolling window holds right now."""
    return BacktestCoverage(**engine._recorder.coverage())


@router.get("/rank", response_model=list[VariantResult])
async def rank(
    engine: BacktestDep,
    window_days: float = Query(default=5.0, ge=0.1, le=5.0),
) -> list[VariantResult]:
    """Strategy tester + ranking: the exit-mode x threshold grid replayed
    over the window, ranked by expectancy, each with its walk-forward
    validation verdict. Only validated variants should be promoted."""
    return [VariantResult(**r) for r in engine.rank(window_days=window_days)]


@router.get("/walkforward", response_model=WalkForwardReport)
async def walkforward(
    engine: BacktestDep,
    exit_mode: str = Query(default="capture", pattern="^(fixed|capture)$"),
    window_days: float = Query(default=5.0, ge=0.1, le=5.0),
) -> WalkForwardReport:
    """Chronological train/test folds — the anti-overfitting gate."""
    return WalkForwardReport(**engine.walk_forward(window_days=window_days, exit_mode=exit_mode))


@router.get("/candles/{mint}", response_model=list[CandleOut])
async def candles(
    mint: str,
    engine: BacktestDep,
    timeframe: str = Query(default="1m", pattern="^(1m|5m|15m)$"),
    limit: int = Query(default=200, ge=10, le=1000),
) -> list[CandleOut]:
    """Aggregated OHLC buckets from recorded samples for one mint."""
    return [CandleOut(**c) for c in engine._recorder.candles(mint, timeframe, limit)]
