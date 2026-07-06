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
    # Trailing stop (pro exit): once a position is up trail_after_pct,
    # close it if price falls trail_drop_pct from its peak — locks profit
    # instead of round-tripping back to the fixed stop.
    trail_after_pct: float | None = Field(default=None, gt=0)
    trail_drop_pct: float | None = Field(default=None, gt=0)
    # Per-bot honest-pricing model (liquid tokens ≈ 0 slippage; illiquid
    # pump.fun launches take a real haircut). Kept per-bot because a 2%
    # haircut that's fine for a sniper destroys a 3%-margin scalper.
    exit_slippage_bps: int = Field(default=100, ge=0, le=1000)
    max_gain_pct: float = Field(default=100.0, gt=0)
    # Seconds to block re-buying a coin after exiting it (anti-churn: you
    # buy a launch once, not repeatedly on every tick).
    reentry_cooldown_s: float = Field(default=600.0, ge=0)


class BotConfigUpdate(BaseModel):
    """Tunable subset of a bot's config — all optional; None = leave as-is.

    Paper mode: changing these adjusts the simulation, never real money.
    """

    usd_per_trade: float | None = Field(default=None, gt=0)
    max_open_positions: int | None = Field(default=None, ge=1, le=10)
    take_profit_pct: float | None = Field(default=None, gt=0, le=1000)
    stop_loss_pct: float | None = Field(default=None, gt=0, le=100)
    trail_after_pct: float | None = Field(default=None, gt=0, le=1000)
    trail_drop_pct: float | None = Field(default=None, gt=0, le=100)
    interval_s: float | None = Field(default=None, ge=2, le=3600)
    exit_slippage_bps: int | None = Field(default=None, ge=0, le=1000)
    max_gain_pct: float | None = Field(default=None, gt=0, le=100000)
    reentry_cooldown_s: float | None = Field(default=None, ge=0, le=86400)


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
