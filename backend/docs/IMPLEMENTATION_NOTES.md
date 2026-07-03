# Implementation Notes

State of the codebase after the foundation delivery (2026-07-03).
Updated same day: `modules/solana` + `modules/market` (Market Intelligence)
delivered — see `docs/MARKET_MODULE.md`. Two defects found only by LIVE
verification, now regression-tested: (1) provider rate guard must delay,
not skip (skip silently dropped 3 of 4 watchlist tokens); (2) DexScreener
exotic-quote pairs report garbage prices (major-quote filter).

## Implemented

| Requirement | Where |
|---|---|
| Configuration loader | `config/settings.py` (pydantic-settings, typed, cached) |
| Environment manager | `.env` / `.env.example`, `Environment` enum, `is_production` |
| Logger | `core/logging.py` (console + JSON modes) |
| Health endpoint | `api/v1/health.py` + `services/health.py` (concurrent probes) |
| Database connection | `database/engine.py` (async SQLAlchemy, lazy) |
| Redis connection | `database/redis_client.py` (lazy) |
| API skeleton | `core/application.py`, `api/router.py`, `/api/v1/*` |
| Error handling | `core/exceptions.py` (hierarchy + one envelope) |
| Dependency injection | `core/dependencies.py` (FastAPI Depends providers) |
| Unit tests | `tests/` — config, health, system, error handling |
| Docker | `Dockerfile`, `docker-compose.yml` (api + postgres + redis) |
| Docs | `docs/` + `README.md` |

## Open TODOs (grep for `TODO(` — every one is tracked in code)

- `TODO(solana)` — RPC client port (modules/solana)
- `TODO(market)` — source clients, snapshot service, SQLite importer
- `TODO(vault)` — vault reader/writer, link checker
- `TODO(agents)` — agent runtime, status registry
- `TODO(api)` — /market, /vault, /agents routers
- `TODO(migrations)` — Alembic replaces create_all

## Duplication report (repository-wide, per foundation analysis)

Nothing deleted — flagged for resolution during migration:

1. **`rpc()` JSON-RPC helper ×4** in the Node layer (`solana-live.mjs`,
   `daily-cycle.mjs`, `market/sources/rpc.mjs`, `risk-engine.mjs`).
   → Resolved by `modules/solana` becoming the single RPC client (Phase 1).
2. **Formatting helpers (`px`, `fmt`, `money`) ×4** across Node scripts.
   → Resolved by `utils/` equivalents when notes rendering is ported.
3. **P&L close logic ×2** (`paper-trade.mjs`, `scalper.mjs`).
   → Resolved by a single paper-trading service (Phase 4).
4. **`scripts/config.json` vs `09 Automation/.env`** — intentional legacy
   fallback; retire config.json when Node layer is decommissioned.
5. **`.agents/skills/` vs `.claude/skills/`** — intentional copy
   (installer output vs Claude Code discovery path). Keep both.

## Suggested repository improvements (not executed without approval)

- Initialize git (`git init`) — the repo currently has no version control;
  this is the highest-value single improvement available.
- Move `market.db`/`history.json` out of OneDrive-synced paths if write
  contention ever appears (SQLite + sync clients can conflict).
- Consolidate the two `.bat` runners per concern into documented tasks.

## Known limitations (deliberate for the foundation)

- `create_all` instead of migrations (Alembic queued, Phase 1).
- No auth on the API — it binds to localhost; auth arrives with the first
  non-read endpoint.
- Health probes hit the public Solana RPC — set `HELIUS_API_KEY` to upgrade.
