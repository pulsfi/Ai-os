# Roadmap

Phased plan from foundation to full AI Operating System. Each phase ends
with working, tested software; no phase starts until the previous one is
verifiably done.

## Phase 0 — Foundation ✅ (this delivery)

- [x] Clean architecture skeleton (api/services/modules/database/models)
- [x] Typed configuration, logging, error handling, DI
- [x] Health + system endpoints, async infrastructure, Docker stack
- [x] Test suite (config, health, error envelope)
- [x] Documentation set (architecture, roadmap, notes, developer guide)

## Phase 1 — Data spine

- [x] `modules/solana`: async RPC client (ends the 4x rpc() duplication) — done 2026-07-03
- [ ] `modules/market`: source clients behind one `PriceSource` protocol
- [ ] Alembic migrations; initial revision from `models/orm`
- [ ] SQLite → PostgreSQL importer for the existing `market.db` history
- [ ] `/api/v1/market` read endpoints (snapshots, watchlist)

## Phase 2 — Collection & vault bridge

- [ ] Background worker (arq vs APScheduler — decide, document) collecting
      snapshots on schedule, replacing `market-manager.mjs` cron duty
- [ ] `modules/vault`: reader/writer + wikilink integrity checker
- [ ] `/api/v1/vault` read-only notes API
- [ ] Node layer decommission checklist (only after parity is proven)

## Phase 3 — Agent runtime

- [ ] `modules/agents`: base Agent (mission/rules from vault, reports to vault)
- [ ] Research + Monitoring agents (read-only) live
- [ ] `/api/v1/agents` status registry
- [ ] Risk engine port (on-chain safety scoring) with unit tests

## Phase 4 — Intelligence (still no live trading)

- [ ] Paper-trading service on PostgreSQL (port of scalper, strategy-pluggable)
- [ ] Performance review reports written to the vault automatically
- [ ] Claude API integration for agent reasoning (research summaries first)

## Phase 5 — Execution gate (explicitly out of scope today)

Entered only when: paper track record is consistently positive over 30+
days, risk engine has test coverage, and key management design (hardware
signer / separate signing service, never keys in this codebase) is approved.
