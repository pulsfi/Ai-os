"""Market module — data collection, storage, and analysis.

Python home for what `09 Automation/market/` (Node) does today. The Node
layer keeps running in production until each piece is ported and verified;
nothing is deleted during the migration.

TODO(market): source clients (coingecko, dexscreener, geckoterminal,
              jupiter, birdeye) behind one `PriceSource` protocol —
              removes the per-script duplication in the Node layer.
TODO(market): SnapshotService writing models.orm.MarketSnapshot to Postgres.
TODO(market): importer for the existing SQLite history (market.db).
TODO(market): cross-source divergence check (>2% disagreement flags), as
              proven necessary by the live JUP/JTO incident on 2026-07-02.
TODO(market): scheduled collection via a worker (arq/APScheduler decision
              pending — see docs/ROADMAP.md phase 2).
"""
