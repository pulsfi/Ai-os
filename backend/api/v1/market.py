"""Market Intelligence endpoints — read-only market data.

Thin routers per the architecture: all logic lives in modules/market.
"""

from fastapi import APIRouter, Query

from core.dependencies import MarketManagerDep
from modules.market.market_models import (
    HistoryPoint,
    MarketStatus,
    TokenInfo,
    TokenMarketData,
)

router = APIRouter()


@router.get("/tokens", response_model=list[TokenMarketData])
async def tokens(manager: MarketManagerDep) -> list[TokenMarketData]:
    """Merged multi-provider data for every tracked token."""
    return await manager.get_watchlist()


@router.get("/trending", response_model=list[TokenMarketData])
async def trending(manager: MarketManagerDep) -> list[TokenMarketData]:
    """Tracked tokens ranked by 24h change, top movers first."""
    return await manager.get_trending()


@router.get("/status", response_model=MarketStatus)
async def status(manager: MarketManagerDep) -> MarketStatus:
    """Module health: providers, cache, scheduler, refresh timestamps."""
    return manager.status()


@router.get("/token/{address}", response_model=TokenInfo)
async def token(address: str, manager: MarketManagerDep) -> TokenInfo:
    """One token: merged market data + on-chain metadata (authorities)."""
    return await manager.get_token_info(address)


@router.get("/history/{address}", response_model=list[HistoryPoint])
async def history(
    address: str,
    manager: MarketManagerDep,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[HistoryPoint]:
    """Stored snapshots for one token, newest first (requires PostgreSQL)."""
    return await manager.get_history(address, limit)
