"""Bot fleet endpoints — live paper-trading bots with REAL controls.

Unlike /agents (vault pipeline, no runtime yet), these bots are actual
asyncio loops in this process: start/stop/restart genuinely change state.
Everything stays paper-mode — the module holds no keys and signs nothing.
"""

from typing import Literal

from fastapi import APIRouter, Query

from core.dependencies import BotManagerDep
from models.schemas.bots import (
    BotControlResult,
    BotPerformance,
    BotStatus,
    BotTrade,
)

router = APIRouter()


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


@router.post("/{bot_id}/{action}", response_model=BotControlResult)
async def control_bot(
    bot_id: str,
    action: Literal["start", "stop", "restart"],
    bots: BotManagerDep,
) -> BotControlResult:
    """Really start/stop/restart the bot's loop; the result says what changed."""
    return await bots.control(bot_id, action)
