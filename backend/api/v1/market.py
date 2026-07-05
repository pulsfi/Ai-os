"""Market Intelligence endpoints — read-only market data.

Thin routers per the architecture: all logic lives in modules/market.
"""

from fastapi import APIRouter, Query

from core.dependencies import HeliusDep, MarketManagerDep, PumpFunDep
from modules.market.helius import TokenActivity
from modules.market.market_models import (
    HistoryPoint,
    MarketStatus,
    TokenInfo,
    TokenMarketData,
)
from modules.market.pumpfun import PumpCoin

router = APIRouter()


@router.get("/activity/{mint}", response_model=TokenActivity)
async def token_activity(
    mint: str, helius: HeliusDep, limit: int = Query(default=50, ge=10, le=100)
) -> TokenActivity:
    """Live flow for a token from Helius parsed transactions: buys vs
    sells, unique wallets, tx rate. Key-gated (HELIUS_API_KEY)."""
    return await helius.get_token_activity(mint, limit)


@router.get("/pumpfun/new", response_model=list[PumpCoin])
async def pumpfun_new(
    pumpfun: PumpFunDep, limit: int = Query(default=20, ge=1, le=50)
) -> list[PumpCoin]:
    """Freshest pump.fun launches, newest first (read-only discovery)."""
    return await pumpfun.get_new_coins(limit)


@router.get("/pumpfun/graduating", response_model=list[PumpCoin])
async def pumpfun_graduating(
    pumpfun: PumpFunDep, limit: int = Query(default=20, ge=1, le=50)
) -> list[PumpCoin]:
    """Highest-cap coins still on the bonding curve — closest to graduation."""
    return await pumpfun.get_graduating(limit)


@router.get("/pumpfun/coin/{mint}", response_model=PumpCoin)
async def pumpfun_coin(mint: str, pumpfun: PumpFunDep) -> PumpCoin:
    """One pump.fun launch by mint address."""
    return await pumpfun.get_coin(mint)


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
