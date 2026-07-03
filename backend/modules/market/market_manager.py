"""Market manager — the module's composition point and public facade.

Owns the shared HTTP client, provider set, cache, and scheduler state.
Everything outside the module (API, agents) talks to the manager; the
internals can be rearranged without breaking a single consumer — the
"future agents consume without code changes" requirement.

READ-ONLY guarantee: nothing in this module can sign, send, or hold keys.
"""

import logging
from datetime import datetime

import httpx

from config import Settings
from core.exceptions import ExternalServiceError, NotFoundError
from database.engine import get_session_factory
from modules.market.market_cache import MarketCache
from modules.market.market_models import (
    HistoryPoint,
    MarketStatus,
    TokenInfo,
    TokenMarketData,
)
from modules.market.market_repository import MarketRepository
from modules.market.market_service import MarketService, build_providers
from modules.market.providers.solana_rpc import SolanaRpcAdapter
from modules.solana import get_rpc_client

logger = logging.getLogger(__name__)


class MarketManager:
    """Coordinates cache -> providers -> merge -> persistence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=8.0)
        self.service = MarketService(build_providers(settings, self._http))
        self.cache = MarketCache(settings)
        self.chain = SolanaRpcAdapter(get_rpc_client(settings))
        # scheduler monitoring state (the scheduler itself lives in market_scheduler)
        self.scheduler_runs = 0
        self.last_refresh: datetime | None = None

    # --- reads (cache-first) ----------------------------------------------

    async def get_token(self, mint: str, *, bypass_cache: bool = False) -> TokenMarketData:
        """Merged market data for one token, cache-first within the TTL."""
        key = f"market:token:{mint}"
        if not bypass_cache and (cached := await self.cache.get(key)) is not None:
            return TokenMarketData.model_validate(cached)
        data = await self.service.fetch_token(mint)
        if not data.sources:
            raise NotFoundError(f"no provider has market data for mint {mint}")
        await self.cache.set(key, data.model_dump(mode="json"))
        return data

    async def get_token_info(self, mint: str) -> TokenInfo:
        """Market data enriched with on-chain metadata (decimals, authorities)."""
        market = await self.get_token(mint)
        decimals, supply, authorities = await self.chain.token_metadata(mint)
        return TokenInfo(market=market, decimals=decimals, supply_ui=supply, authorities=authorities)

    async def get_watchlist(self) -> list[TokenMarketData]:
        """Merged data for every tracked token (partial failures tolerated)."""
        out: list[TokenMarketData] = []
        for mint in self._settings.market_watchlist:
            try:
                out.append(await self.get_token(mint))
            except NotFoundError:
                logger.warning("watchlist mint %s has no data from any provider", mint[:8])
        return out

    async def get_trending(self) -> list[TokenMarketData]:
        """Tracked tokens ranked by 24h change (top movers first).

        TODO(market): plug a discovery provider (GeckoTerminal trending)
        so trending covers the whole chain, not only the watchlist.
        """
        tokens = await self.get_watchlist()
        return sorted(tokens, key=lambda t: t.change_24h or 0, reverse=True)

    async def get_history(self, mint: str, limit: int = 100) -> list[HistoryPoint]:
        """Stored snapshots from PostgreSQL (the only DB-dependent read)."""
        try:
            async with get_session_factory(self._settings)() as session:
                return await MarketRepository(session).history(mint, limit)
        except Exception as exc:  # noqa: BLE001 — translate to the error envelope
            raise ExternalServiceError("history unavailable: database unreachable") from exc

    # --- writes (scheduler only) -------------------------------------------

    async def refresh_all(self) -> int:
        """Refresh every watchlist token and persist snapshots. Returns count."""
        stored = 0
        for mint in self._settings.market_watchlist:
            try:
                data = await self.get_token(mint, bypass_cache=True)
                async with get_session_factory(self._settings)() as session:
                    await MarketRepository(session).insert_snapshot(data)
                stored += 1
            except Exception as exc:  # noqa: BLE001 — one bad token can't stop the sweep
                logger.warning("refresh failed for %s: %s", mint[:8], exc)
        self.scheduler_runs += 1
        from utils.time import utc_now

        self.last_refresh = utc_now()
        logger.info("market refresh complete: %d/%d snapshots stored", stored, len(self._settings.market_watchlist))
        return stored

    # --- monitoring ---------------------------------------------------------

    def status(self) -> MarketStatus:
        """Everything the Monitoring Agent needs about this module."""
        return MarketStatus(
            providers=self.service.provider_statuses(),
            cache_backend=self.cache.backend,
            cache_hits=self.cache.hits,
            cache_misses=self.cache.misses,
            scheduler_enabled=self._settings.market_refresh_enabled,
            scheduler_interval_s=self._settings.market_refresh_seconds,
            scheduler_runs=self.scheduler_runs,
            last_refresh=self.last_refresh,
            tracked_tokens=len(self._settings.market_watchlist),
        )

    async def aclose(self) -> None:
        """Release the shared HTTP client (lifespan shutdown)."""
        await self._http.aclose()


# --- process-wide singleton (same pattern as database.engine) --------------

_manager: MarketManager | None = None


def get_market_manager(settings: Settings) -> MarketManager:
    """Return the shared MarketManager, creating it on first use."""
    global _manager
    if _manager is None:
        _manager = MarketManager(settings)
        logger.info("Market manager created (%d tracked tokens)", len(settings.market_watchlist))
    return _manager


async def close_market_manager() -> None:
    """Dispose the shared manager. Called from the app lifespan shutdown."""
    global _manager
    if _manager is not None:
        await _manager.aclose()
        _manager = None
        logger.info("Market manager closed")
