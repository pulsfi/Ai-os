"""Market Intelligence module — READ-ONLY market data collection.

Never buys, sells, signs, or holds keys. Its sole job: collect, validate,
store, and expose live market data for the API and the agents
(Research, Risk, Strategy, Monitoring, Learning).

Layout (all internal — consumers import from this package root):
    market_manager     composition point & facade  <- start here
    market_service     provider fan-out + merge + divergence validation
    providers/         one isolated adapter per source (swap point)
    market_cache       Redis w/ memory fallback (rate-limit shield)
    market_repository  tokens + snapshot history (PostgreSQL)
    market_scheduler   configurable async refresh loop
    price_service / token_service / liquidity_service / volume_service
                       narrow agent-facing facades (ISP)

Done: 5 provider adapters, merge+divergence, cache, repo, scheduler,
      REST endpoints, monitoring, tests.
TODO(market): chain-wide trending via a discovery provider.
TODO(market): importer for the legacy Node SQLite history (market.db).
"""

from modules.market.market_manager import (
    MarketManager,
    close_market_manager,
    get_market_manager,
)

__all__ = ["MarketManager", "close_market_manager", "get_market_manager"]
