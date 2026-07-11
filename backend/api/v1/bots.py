"""Bot fleet endpoints — live paper-trading bots with REAL controls.

Unlike /agents (vault pipeline, no runtime yet), these bots are actual
asyncio loops in this process: start/stop/restart genuinely change state.
Everything stays paper-mode — the module holds no keys and signs nothing.
"""

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.dependencies import BotManagerDep
from models.schemas.bots import (
    BotConfigUpdate,
    BotControlResult,
    BotInsights,
    BotPerformance,
    BotStatus,
    BotTrade,
    SniperTelemetry,
)

router = APIRouter()


class ResetResult(BaseModel):
    """Outcome of wiping the paper track record."""

    wiped: int
    detail: str


@router.post("/reset", response_model=ResetResult)
async def reset_ledger(bots: BotManagerDep) -> ResetResult:
    """Wipe the paper trade record for a clean start (e.g. after a pricing
    model change). Paper data only — no real funds are involved."""
    n = bots.reset_ledger()
    return ResetResult(
        wiped=n,
        detail=f"Wiped {n} paper trades. The track record now restarts under "
        "the current (honest) pricing model.",
    )


@router.get("", response_model=list[BotStatus])
async def list_bots(bots: BotManagerDep) -> list[BotStatus]:
    """Every bot: config, runtime state, and ledger stats."""
    return bots.statuses()


@router.get("/performance", response_model=list[BotPerformance])
async def performance(bots: BotManagerDep) -> list[BotPerformance]:
    """Track record per bot + the whole fleet: equity curve of REALIZED
    PnL, win rate, avg/best/worst trade. The evidence the Stage 5 gate
    will be judged on."""
    return bots.performance()


@router.get("/telemetry", response_model=SniperTelemetry)
async def telemetry(bots: BotManagerDep) -> SniperTelemetry:
    """The sniper's live signals funnel: launches seen, rejections with the
    exact reason (whale concentration, weak momentum, rug risk, …), trades
    executed, and average confidence — why it is or isn't trading."""
    return bots.sniper_telemetry()


@router.get("/insights", response_model=BotInsights)
async def insights(
    bots: BotManagerDep, bot_id: str = Query(default="sniper")
) -> BotInsights:
    """Which scoring factors separated winners from losers (parsed from real
    trade notes). Evidence for reviewing weights — never auto-applied."""
    return bots.insights(bot_id)


@router.get("/trades", response_model=list[BotTrade])
async def all_trades(
    bots: BotManagerDep, limit: int = Query(default=50, ge=1, le=500)
) -> list[BotTrade]:
    """Fleet-wide paper trade log, newest first."""
    return bots.trades(None, limit)


@router.get("/{bot_id}/trades", response_model=list[BotTrade])
async def bot_trades(
    bot_id: str, bots: BotManagerDep, limit: int = Query(default=50, ge=1, le=500)
) -> list[BotTrade]:
    """One bot's paper trade log, newest first (404 for unknown bots)."""
    return bots.trades(bot_id, limit)


@router.patch("/{bot_id}/config", response_model=BotStatus)
async def update_bot_config(
    bot_id: str, update: BotConfigUpdate, bots: BotManagerDep
) -> BotStatus:
    """Tune a bot's parameters (take-profit, size, …). Paper only; persists
    across restarts. Returns the bot's fresh status."""
    return bots.update_config(bot_id, update)


@router.post("/{bot_id}/{action}", response_model=BotControlResult)
async def control_bot(
    bot_id: str,
    action: Literal["start", "stop", "restart"],
    bots: BotManagerDep,
) -> BotControlResult:
    """Really start/stop/restart the bot's loop; the result says what changed."""
    return await bots.control(bot_id, action)
