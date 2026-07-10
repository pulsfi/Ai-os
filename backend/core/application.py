"""Application factory and lifespan — the composition root.

`create_app()` builds a fully-wired FastAPI instance with no import-time
side effects, so tests can create isolated apps and uvicorn gets the same
object via `main:app`.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.router import api_router
from config import Settings, get_settings
from core.exceptions import register_exception_handlers
from core.logging import setup_logging
from database.engine import dispose_engine
from database.redis_client import close_redis
from modules.agents import close_agent_runtime, get_agent_runtime
from modules.alerts import close_alerts
from modules.bots import close_bot_manager, get_bot_manager
from modules.chat import close_chat_service
from modules.execution import close_executor, close_swap_builder
from modules.market import close_market_manager, get_market_manager
from modules.market.helius import close_helius_client
from modules.market.pumpfun import close_pumpfun_client
from modules.market.pumpportal import close_launch_stream
from modules.market.market_scheduler import MarketScheduler
from modules.solana import close_rpc_client
from modules.vault import get_vault_service
from modules.vault.report_scheduler import DailyReportScheduler

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
    scheduler: MarketScheduler | None = None
    if settings.market_refresh_enabled:
        scheduler = MarketScheduler(
            get_market_manager(settings), settings.market_refresh_seconds
        )
        scheduler.start()
    if settings.bots_enabled and settings.bots_autostart:
        # Paper-mode fleet trades continuously from boot (virtual USD only).
        get_bot_manager(settings).start_all()
    report_scheduler: DailyReportScheduler | None = None
    if settings.bots_enabled and settings.daily_report_enabled:
        report_scheduler = DailyReportScheduler(
            get_bot_manager(settings),
            get_vault_service(settings),
            settings.daily_report_hour_utc,
        )
        report_scheduler.start()
    if settings.agents_runtime_enabled:
        # The 7-agent pipeline runs live over the real modules (read-only).
        get_agent_runtime(settings).start()
    yield
    await close_agent_runtime()
    await close_alerts()
    if report_scheduler is not None:
        await report_scheduler.stop()
    if scheduler is not None:
        await scheduler.stop()
    await close_bot_manager()
    await close_market_manager()
    await close_pumpfun_client()
    await close_launch_stream()
    await close_helius_client()
    await close_chat_service()
    await close_executor()
    await close_swap_builder()
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

    # --- API auth gate ---------------------------------------------------
    # When a token is configured, every request must present it (header
    # X-API-Key or Authorization: Bearer). Health checks stay open so
    # uptime monitors work; the WebSocket authenticates via ?token= inside
    # its own handler (browsers can't set WS headers), so it's exempt here.
    if settings.api_auth_token:
        token = settings.api_auth_token
        prefix = settings.api_v1_prefix

        @app.middleware("http")
        async def _auth(request: Request, call_next):  # type: ignore[no-untyped-def]
            path = request.url.path
            exempt = (
                not path.startswith(prefix)
                or path.endswith(("/health", "/ping"))
                or "/ws" in path
                or request.method == "OPTIONS"  # CORS preflight
            )
            if not exempt:
                provided = request.headers.get("x-api-key", "")
                if not provided:
                    auth = request.headers.get("authorization", "")
                    if auth.lower().startswith("bearer "):
                        provided = auth[7:]
                if provided != token:
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": {
                                "code": "unauthorized",
                                "message": "Missing or invalid API key.",
                                "details": None,
                            }
                        },
                    )
            return await call_next(request)

    # The Next.js frontend calls this API from the browser; without CORS
    # every cross-origin request is blocked before it reaches a route.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app
