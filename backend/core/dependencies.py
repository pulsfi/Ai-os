"""Dependency injection providers — the only place wiring happens.

FastAPI's `Depends` is our DI container: routers declare what they need,
these providers construct it. Services never instantiate their own
infrastructure (Dependency Inversion — the D in SOLID).

    @router.get("/thing")
    async def read_thing(svc: HealthService = Depends(get_health_service)): ...
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from database.engine import get_session_factory
from database.redis_client import get_redis
from modules.agents import AgentsService, get_agents_service
from modules.bots import BotManager, get_bot_manager
from modules.chat import ChatService, get_chat_service
from modules.market import MarketManager, get_market_manager
from modules.market.pumpfun import PumpFunClient, get_pumpfun_client
from modules.solana import RpcClient, get_rpc_client
from modules.trading import PaperTradingService, get_paper_trading_service
from modules.vault import VaultService, get_vault_service
from services.health import HealthService

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db_session(settings: SettingsDep) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session (commit/rollback safe)."""
    factory = get_session_factory(settings)
    async with factory() as session:
        yield session


async def get_redis_client(settings: SettingsDep) -> Redis:
    """Provide the shared Redis client."""
    return get_redis(settings)


def get_health_service(settings: SettingsDep) -> HealthService:
    """Provide the health application service."""
    return HealthService(settings)


def get_solana_client(settings: SettingsDep) -> RpcClient:
    """Provide the shared Solana RPC client (read-only chain access)."""
    return get_rpc_client(settings)


def get_market(settings: SettingsDep) -> MarketManager:
    """Provide the shared Market Intelligence manager (read-only data)."""
    return get_market_manager(settings)


def get_chat(settings: SettingsDep) -> ChatService:
    """Provide the Claude chat service (key-gated)."""
    return get_chat_service(settings)


def get_agents(settings: SettingsDep) -> AgentsService:
    """Provide the read-only vault agents service."""
    return get_agents_service(settings)


def get_pumpfun(settings: SettingsDep) -> PumpFunClient:
    """Provide the read-only pump.fun discovery client."""
    return get_pumpfun_client(settings)


def get_paper_trading(settings: SettingsDep) -> PaperTradingService:
    """Provide the read-only paper-trading ledger view."""
    return get_paper_trading_service(settings)


def get_bots(settings: SettingsDep) -> BotManager:
    """Provide the bot fleet manager (paper-mode runtime)."""
    return get_bot_manager(settings)


def get_vault(settings: SettingsDep) -> VaultService:
    """Provide the read-only vault notes bridge."""
    return get_vault_service(settings)


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
RedisDep = Annotated[Redis, Depends(get_redis_client)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
SolanaClientDep = Annotated[RpcClient, Depends(get_solana_client)]
MarketManagerDep = Annotated[MarketManager, Depends(get_market)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat)]
AgentsServiceDep = Annotated[AgentsService, Depends(get_agents)]
PumpFunDep = Annotated[PumpFunClient, Depends(get_pumpfun)]
PaperTradingDep = Annotated[PaperTradingService, Depends(get_paper_trading)]
BotManagerDep = Annotated[BotManager, Depends(get_bots)]
VaultServiceDep = Annotated[VaultService, Depends(get_vault)]
