"""Trading endpoints — read-only paper-trading ledger.

No buy/sell endpoints exist by design: execution is the Node scalper's
job (paper mode), and live execution stays behind the Stage 5 gate.
Endpoints are sync `def` so SQLite reads run in FastAPI's threadpool.
"""

from fastapi import APIRouter, Query

from core.dependencies import PaperTradingDep
from models.schemas.trading import PaperSummary, PaperTrade

router = APIRouter()


@router.get("/summary", response_model=PaperSummary)
def paper_summary(paper: PaperTradingDep) -> PaperSummary:
    """Paper track record: totals, realized PnL, win rate."""
    return paper.summary()


@router.get("/trades", response_model=list[PaperTrade])
def paper_trades(
    paper: PaperTradingDep,
    limit: int = Query(default=50, ge=1, le=500),
    status: str | None = Query(default=None, pattern="^(open|closed)$"),
) -> list[PaperTrade]:
    """Trade log, newest first; filter with ?status=open|closed."""
    return paper.trades(limit=limit, status=status)
