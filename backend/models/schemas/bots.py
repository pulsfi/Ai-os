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


class ProfitTierModel(BaseModel):
    """One rung of the profit ladder: sell `sell_pct`% of the ORIGINAL
    position when unrealized gain first reaches `gain_pct`%."""

    gain_pct: float = Field(gt=0, le=2000)
    sell_pct: float = Field(gt=0, le=100)


def _default_tiers() -> list["ProfitTierModel"]:
    return [
        ProfitTierModel(gain_pct=g, sell_pct=s)
        for g, s in [(5, 10), (10, 10), (25, 20), (50, 10), (100, 15),
                     (250, 10), (500, 10), (1000, 5), (2000, 10)]
    ]


class ProfitCaptureSettings(BaseModel):
    """Dynamic Profit Capture — tiered scale-out with a tightening trail.

    When enabled it REPLACES the bot's fixed take-profit / trailing /
    break-even exits; the stop-loss, stall exit, and rug protections stay
    as the immediate risk floor. Paper and live share this logic."""

    enabled: bool = False
    tiers: list[ProfitTierModel] = Field(default_factory=_default_tiers)
    base_trail_drop_pct: float = Field(default=15.0, gt=0, le=100)
    min_trail_drop_pct: float = Field(default=4.0, gt=0, le=100)
    decay_after_s: float = Field(default=300.0, gt=0)


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
    # Break-even stop: once the peak gain clears this, a fallback exit near
    # entry replaces the full stop-loss (a winner never becomes a -18% loss).
    break_even_at_pct: float | None = Field(default=None, gt=0)
    # Stall exit (time stop): a momentum entry that hasn't reached
    # stall_min_gain_pct within stall_exit_s is a failed impulse — exit
    # ~flat instead of bleeding down to the full stop-loss. Live evidence
    # (46 trades): stop-losses cost -$117 while every other exit type was
    # roughly breakeven-to-positive.
    stall_exit_s: float | None = Field(default=None, gt=0)
    stall_min_gain_pct: float = Field(default=3.0, ge=0, le=100)
    # Per-bot honest-pricing model (liquid tokens ≈ 0 slippage; illiquid
    # pump.fun launches take a real haircut). Kept per-bot because a 2%
    # haircut that's fine for a sniper destroys a 3%-margin scalper.
    exit_slippage_bps: int = Field(default=100, ge=0, le=1000)
    max_gain_pct: float = Field(default=100.0, gt=0)
    # Seconds to block re-buying a coin after exiting it (anti-churn: you
    # buy a launch once, not repeatedly on every tick).
    reentry_cooldown_s: float = Field(default=600.0, ge=0)
    # One shot per coin: once traded, NEVER re-enter that mint (there's an
    # ocean of other coins). On for launch bots; off for liquid majors.
    one_shot_per_mint: bool = False
    # Execution threshold: minimum confidence score (0-100) a scored entry
    # must reach. Only strategies that score (the sniper) use it.
    min_confidence: float = Field(default=55.0, ge=0, le=100)
    # Dynamic Profit Capture (tiered scale-out). Disabled = legacy exits.
    profit_capture: ProfitCaptureSettings = Field(default_factory=ProfitCaptureSettings)


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
    break_even_at_pct: float | None = Field(default=None, gt=0, le=1000)
    stall_exit_s: float | None = Field(default=None, gt=0, le=3600)
    stall_min_gain_pct: float | None = Field(default=None, ge=0, le=100)
    interval_s: float | None = Field(default=None, ge=2, le=3600)
    exit_slippage_bps: int | None = Field(default=None, ge=0, le=1000)
    max_gain_pct: float | None = Field(default=None, gt=0, le=100000)
    reentry_cooldown_s: float | None = Field(default=None, ge=0, le=86400)
    one_shot_per_mint: bool | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=100)
    # Whole-object replace from the Tune modal's Profit Capture editor.
    profit_capture: ProfitCaptureSettings | None = None


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
    # Active expectancy-guard pause reason (None = trading normally).
    risk_note: str | None = None


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
    # The numbers that decide long-term viability (win rate alone lies):
    profit_factor: float | None = None  # gross wins / gross losses
    expectancy_usd: float | None = None  # avg PnL per trade
    avg_win_pct: float | None = None
    avg_loss_pct: float | None = None
    max_drawdown_usd: float | None = None  # worst peak-to-trough of the curve
    today_pnl_usd: float = 0.0
    curve: list[EquityPoint] = []


class PortfolioRisk(BaseModel):
    """Fleet-wide risk snapshot: exposure, budgets, worst case, concentration."""

    open_positions: int = 0
    open_exposure_usd: float = 0.0
    max_exposure_usd: float = 0.0
    exposure_used_pct: float = 0.0
    today_pnl_usd: float = 0.0
    daily_loss_limit_usd: float = 0.0
    daily_budget_left_usd: float = 0.0
    # Sum over open positions of size x stop distance: what today's worst
    # case adds if every stop fires at its level (gaps can exceed it).
    risk_at_stop_usd: float = 0.0
    exposure_by_symbol: dict[str, float] = {}
    entries_blocked: str | None = None


class RejectionRecord(BaseModel):
    """One launch the sniper evaluated and turned down — with the reasons."""

    ts: str
    mint: str
    symbol: str
    score: float
    threshold: float | None = None
    reasons: list[str]
    categories: list[str]


class SniperTelemetry(BaseModel):
    """The signals funnel: everything seen, why rejects rejected, what ran.

    Answers 'why isn't it trading?' with evidence instead of guesses."""

    bot_id: str = "sniper"
    signals_detected: int = 0
    signals_approved: int = 0
    trades_executed: int = 0
    rejected_recent: int = 0
    avg_confidence: float | None = None
    execution_threshold: float | None = None
    # Stream health — when flow_healthy is False, the breadth gate degrades
    # to a scored factor instead of an unsatisfiable hard requirement.
    stream_connected: bool = False
    flow_healthy: bool = False
    stream_trades_seen: int = 0
    reject_reasons: dict[str, int] = {}
    recent_rejections: list[RejectionRecord] = []


class FactorInsight(BaseModel):
    """How one scoring factor differed between winning and losing entries."""

    name: str
    winners_avg: float | None = None
    losers_avg: float | None = None
    edge: float | None = None  # winners_avg - losers_avg


class BotInsights(BaseModel):
    """Win/loss factor analysis parsed from real trade notes — evidence for
    reviewing scoring weights. Deliberately NOT auto-applied: on small
    samples, silent self-tuning overfits noise."""

    bot_id: str
    closed_analyzed: int
    wins: int
    losses: int
    factors: list[FactorInsight]
    note: str
