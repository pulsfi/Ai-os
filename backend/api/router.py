"""Top-level API router — mounts every versioned sub-router.

Adding a new domain endpoint = add a router module under api/v1/ and
include it here. Nothing else changes (Open/Closed principle).
"""

from fastapi import APIRouter

from api.v1 import (
    agents,
    alerts,
    backtest,
    bots,
    chat,
    execution,
    health,
    market,
    solana,
    system,
    trading,
    vault,
    ws,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(solana.router, prefix="/solana", tags=["solana"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(trading.router, prefix="/trading", tags=["trading"])
api_router.include_router(bots.router, prefix="/bots", tags=["bots"])
api_router.include_router(ws.router, prefix="/ws", tags=["ws"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(execution.router, prefix="/execution", tags=["execution"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
