"""Trading API contracts — read-only paper-trading ledger views."""

from pydantic import BaseModel, Field


class PaperTrade(BaseModel):
    """One row of the paper_trades ledger (written by the Node scalper)."""

    id: int
    symbol: str
    mint: str | None = None
    usd_size: float
    entry_price: float
    entry_ts: str
    exit_price: float | None = None
    exit_ts: str | None = None
    pnl_usd: float | None = None
    pnl_pct: float | None = None
    reasoning: str | None = None
    exit_note: str | None = None
    status: str  # open | closed


class PaperSummary(BaseModel):
    """The paper track record at a glance.

    `available` is False when the ledger DB does not exist yet — the UI
    shows that state honestly instead of zeros pretending to be data.
    """

    available: bool
    total_trades: int = 0
    open_trades: int = 0
    closed_trades: int = 0
    realized_pnl_usd: float = 0.0
    win_rate_pct: float | None = Field(
        default=None, description="Share of closed trades with positive PnL"
    )
    last_entry_ts: str | None = None
    snapshots_stored: int = 0
