# Market Intelligence Module

READ-ONLY market data: collect, validate, store, expose. This module can
never buy, sell, sign, or hold keys — no such code paths exist.

## Architecture

```
                       ┌────────────────────────────────────────────┐
                       │                api/v1/market               │
                       │  /tokens /trending /token/{a} /history /status
                       └──────────────────────┬─────────────────────┘
                                              │ DI (core/dependencies)
                                              ▼
                       ┌────────────────────────────────────────────┐
                       │           MarketManager (facade)           │
                       │  cache-first reads · refresh writes · stats │
                       └───┬───────────────┬──────────────┬─────────┘
                           │               │              │
                 ┌─────────▼───────┐ ┌─────▼──────┐ ┌─────▼─────────┐
                 │  MarketService  │ │ MarketCache│ │MarketRepository│
                 │ fan-out + merge │ │ Redis→mem  │ │ tokens/snaps   │
                 │ + divergence    │ │ TTL guard  │ │ (PostgreSQL)   │
                 └─────────┬───────┘ └────────────┘ └───────────────┘
                           │ MarketProvider interface (the swap point)
      ┌──────────┬─────────┼──────────┬─────────────┐
      ▼          ▼         ▼          ▼             ▼
 DexScreener CoinGecko  Jupiter   Birdeye*   SolanaRpcAdapter
 (pairs,liq) (mcap,vol) (price)   (*needs key) (metadata, authorities)
```

Agent-facing facades (Interface Segregation): `price_service`,
`token_service`, `liquidity_service`, `volume_service` — narrow surfaces
so future agents (Research/Risk/Strategy/Monitoring/Learning) consume
data without depending on module internals.

## Data flow

```
request → cache hit? ──yes──► return (TTL fresh, zero provider calls)
             │no
             ▼
   all providers concurrently (rate guard DELAYS to provider pace)
             ▼
   merge: field preference dexscreener > coingecko > jupiter > birdeye
   validate: cross-provider price divergence >2% → warn + report
             ▼
   cache set (TTL) ──► [scheduler runs only] repository.insert_snapshot
                        (token_id, ts) UNIQUE → no duplicate rows
```

## Endpoints

| Endpoint | Returns | Needs DB |
|---|---|---|
| `GET /api/v1/market/tokens` | merged data for the watchlist | no |
| `GET /api/v1/market/trending` | watchlist ranked by 24h change | no |
| `GET /api/v1/market/token/{address}` | market + decimals/supply/authorities | no |
| `GET /api/v1/market/history/{address}?limit=` | stored snapshots, newest first | yes |
| `GET /api/v1/market/status` | providers, cache, scheduler monitoring | no |

## Configuration (`.env`)

`BIRDEYE_API_KEY`, `MARKET_CACHE_TTL_SECONDS` (30), `MARKET_REFRESH_ENABLED`
(false), `MARKET_REFRESH_SECONDS` (300), `MARKET_PROVIDER_MIN_INTERVAL_SECONDS`
(1.0), `MARKET_WATCHLIST` (JSON list of mints; default SOL/JUP/BONK/WIF).

## Storage

`tokens` (normalized identity) ← `market_snapshots` (history; unique
`(token_id, ts)`). Migrations: `database/migrations/*.sql` applied by
`python -m scripts.migrate`.

## Design decisions

1. **Providers behind one interface** — `MarketProvider` is the swap point;
   adding a source touches zero service code.
2. **Rate guard delays, never drops** — proven live: skip-behavior silently
   lost 3 of 4 watchlist tokens on a burst; pacing keeps both the data and
   the provider limits.
3. **Merge with preference + divergence check** — DEX-level data beats
   aggregator estimates; >2% cross-provider disagreement is surfaced to
   consumers (the JUP/JTO bad-pool lesson, now a regression test).
4. **Cache is the rate-limit shield** — reads inside the TTL never touch a
   provider; Redis failure degrades to in-process memory, reported in /status.
5. **DB is enrichment, not a dependency** — live reads work with PostgreSQL
   down; only /history requires it (clean 502 envelope otherwise).
6. **Scheduler is opt-in** — a plain asyncio task owned by the app lifespan;
   no worker framework until job count justifies one (Phase 2 decision).
7. **Endpoint-level dedupe** — uniqueness enforced by schema constraint,
   not application discipline.

## Remaining improvements

- Chain-wide trending via a discovery provider (GeckoTerminal)
- CoinGecko id resolution for arbitrary mints (currently known-mint map)
- Importer for the legacy Node SQLite history (`market.db`)
- Alembic to replace the SQL-file migration runner
- Respect `Retry-After` headers on 429 responses
- Integration test suite against docker-compose (marked `integration`)
