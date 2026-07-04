"""Top-level API router — mounts every versioned sub-router.

Adding a new domain endpoint = add a router module under api/v1/ and
include it here. Nothing else changes (Open/Closed principle).
"""

from fastapi import APIRouter

from api.v1 import agents, chat, health, market, solana, system, trading

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(solana.router, prefix="/solana", tags=["solana"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(trading.router, prefix="/trading", tags=["trading"])

# TODO(api): /vault endpoints once services/vault lands (notes bridge)
