"""Bot fleet API contracts.

PAPER MODE ONLY: bots trade virtual USD against live market data. There
are no wallets, no keys, and no transaction signing anywhere in this
module tree — live execution stays behind the roadmap's Stage 5 gate.
"""

from enum import Enum

from pydantic import BaseModel, Field


class BotState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


class BotConfig(BaseModel):
    """Static definition of one bot in the fleet."""

    id: str
    name: str
    strategy: str
    description: str
    interval_s: float = Field(gt=0, description="Seconds between ticks")
    usd_per_trade: float = Field(gt=0, description="Virtual position size")
    max_open_positions: int = Field(ge=1)
    take_profit_pct: float = Field(gt=0)
    stop_loss_pct: float = Field(gt=0, description="Positive number, e.g. 15 = -15%")
    max_hold_s: float = Field(gt=0, description="Force-close positions older than this")


class BotStatus(BaseModel):
    """Live view of one bot: config + runtime + ledger stats."""

    config: BotConfig
    state: BotState
    started_at: str | None = None
    ticks: int = 0
    errors: int = 0
    last_error: str | None = None
    open_positions: int = 0
    closed_trades: int = 0
    realized_pnl_usd: float = 0.0
    win_rate_pct: float | None = None


class BotTrade(BaseModel):
    """One paper trade from the bot ledger."""

    id: int
    bot_id: str
    mint: str
    symbol: str
    usd_size: float
    entry_price: float
    entry_ts: str
    exit_price: float | None = None
    exit_ts: str | None = None
    pnl_usd: float | None = None
    pnl_pct: float | None = None
    status: str
    entry_note: str | None = None
    exit_note: str | None = None


class BotControlResult(BaseModel):
    """Outcome of start/stop/restart — real state changes, reported honestly."""

    bot_id: str
    action: str
    accepted: bool
    state: BotState
    detail: str


class EquityPoint(BaseModel):
    """One step of the cumulative realized-PnL curve (a closed trade)."""

    ts: str  # exit timestamp of the trade that moved equity
    equity_usd: float  # cumulative realized PnL after this trade


class BotPerformance(BaseModel):
    """Track record of one bot (or the whole fleet as id 'fleet')."""

    bot_id: str
    name: str
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate_pct: float | None = None
    realized_pnl_usd: float = 0.0
    avg_pnl_pct: float | None = None
    best_trade_pct: float | None = None
    worst_trade_pct: float | None = None
    curve: list[EquityPoint] = []
