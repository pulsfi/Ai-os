"""Execution-layer contracts (Stage 5).

SAFETY MODEL — read before touching anything here:
  * The system ships DISARMED. `armed` is False unless EXECUTION_ARMED=true
    is set in the environment, which only the operator can do.
  * The only implemented execution mode is DRY_RUN: it fetches real
    quotes and records what it WOULD trade, but signs nothing and sends
    nothing. There is no private key anywhere in this module tree.
  * Every order passes the RiskEngine first (size cap, daily-loss halt,
    concurrency cap, kill switch). A denied order never executes.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    DRY_RUN = "dry_run"  # simulate only — the sole implemented mode
    LIVE = "live"  # real money — intentionally NOT implemented yet


class RiskLimits(BaseModel):
    """The hard limits every order is checked against."""

    max_position_usd: float
    daily_loss_limit_usd: float = Field(description="Trading halts once daily loss hits this")
    max_concurrent_positions: int
    max_slippage_bps: int


class ExecutionStatus(BaseModel):
    """Is live execution on? (It isn't, by default — and says so.)"""

    armed: bool
    mode: ExecutionMode
    kill_switch: bool = Field(description="True = all execution halted")
    live_available: bool = Field(description="Is a real-money path implemented + wired?")
    limits: RiskLimits
    realized_pnl_today_usd: float
    reason: str = Field(description="Plain-language current state")


class OrderRequest(BaseModel):
    """An intended swap (used by the dry-run path and risk checks)."""

    mint: str
    symbol: str
    side: str = Field(pattern="^(buy|sell)$")
    usd_size: float = Field(gt=0)


class OrderResult(BaseModel):
    """Outcome of an order attempt — dry-run fills are clearly labeled."""

    accepted: bool
    mode: ExecutionMode
    mint: str
    symbol: str
    side: str
    usd_size: float
    simulated_fill_price: float | None = None
    quote_out_amount: str | None = Field(default=None, description="Raw Jupiter out amount")
    price_impact_pct: float | None = None
    detail: str


class WalletBalance(BaseModel):
    """Read-only balance view of a PUBLIC address (never a key)."""

    address: str
    sol: float
    lamports: int


class BuildBuyRequest(BaseModel):
    """Ask the backend to BUILD (not sign) a SOL -> token swap."""

    user_pubkey: str = Field(min_length=32, max_length=44)
    mint: str = Field(min_length=32, max_length=44)
    usd_size: float = Field(gt=0)


class BuildSellRequest(BaseModel):
    """Ask the backend to BUILD (not sign) a token -> SOL swap (full size)."""

    user_pubkey: str = Field(min_length=32, max_length=44)
    mint: str = Field(min_length=32, max_length=44)


class BuiltSwap(BaseModel):
    """An UNSIGNED transaction for the user's wallet to approve.

    The backend cannot execute this — only the holder of the key (the
    user's Phantom wallet) can sign it, one explicit click per trade.
    """

    swap_transaction_b64: str
    description: str
    price_impact_pct: float | None = None
    out_amount: str | None = None
    warning: str = (
        "Review this trade in your wallet before approving. Meme-coin "
        "trades can lose their full value. The app never sees your key."
    )


class ReadinessCriterion(BaseModel):
    """One go-live gate: where the paper record stands vs the target."""

    name: str
    target: str
    actual: str
    passed: bool


class GoLiveReadiness(BaseModel):
    """The scorecard that must be fully green before real money is justified."""

    ready: bool
    criteria: list[ReadinessCriterion]
    summary: str
