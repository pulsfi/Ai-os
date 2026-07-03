"""Application factory and lifespan — the composition root.

`create_app()` builds a fully-wired FastAPI instance with no import-time
side effects, so tests can create isolated apps and uvicorn gets the same
object via `main:app`.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.router import api_router
from config import Settings, get_settings
from core.exceptions import register_exception_handlers
from core.logging import setup_logging
from database.engine import dispose_engine
from database.redis_client import close_redis
from modules.solana import close_rpc_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks: log identity on boot, release pools on exit."""
    settings: Settings = app.state.settings
    logger.info(
        "%s v%s starting (env=%s, debug=%s)",
        settings.app_name,
        settings.app_version,
        settings.environment.value,
        settings.debug,
    )
    yield
    await dispose_engine()
    await close_redis()
    await close_rpc_client()
    logger.info("%s stopped cleanly", settings.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and wire the application.

    Args:
        settings: optional override (tests inject custom settings here);
                  defaults to the environment-derived singleton.
    """
    settings = settings or get_settings()
    setup_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        # OpenAPI docs exposed only outside production by default.
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app
