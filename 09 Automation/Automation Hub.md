---
tags: [automation, index]
created: 2026-07-02
---

# ⚙️ Automation Hub

Workflows, pipelines, and schedules that keep the [[Agent Control Center]] running without manual effort.

← Back to [[Home]]

## 🟢 Live Automations

- [x] **[[Solana Live Feed]]** — real-time mainnet data (price, TPS, epoch, validators) → [[Solana Live]] (went live 2026-07-02)
- [x] **Daily Learning Cycle** — self-trains on live data day by day → [[Training Log]] (went live 2026-07-02, tested with a simulated day 2). Run: `daily.bat` in `scripts/`, ~1 second per cycle. Auto-creates the daily note and raises 🔴 alerts to the [[Monitoring Agent]] on ±10% moves.
- [x] **[[Market Data Service]]** — multi-source watchlist (CoinGecko + DexScreener + Jupiter + RPC) → SQLite database → [[Market Watch]] with agent risk flags (went live 2026-07-02)
- [x] **Paper Trading Engine** — hypothetical trades at real live prices → [[Paper Trading]] (went live 2026-07-02; first position opened same day)
- [x] **Risk Engine (Stage 4)** — automated on-chain token safety scoring: mint/freeze authority, liquidity, holder concentration, pool age → `market/risk-engine.mjs` (went live 2026-07-02; BONK scored 0/10 ✅ on first run)
- [x] **⚡ Meme Scalper (paper)** — autonomous scalp loop: trending-pool radar → risk gate → momentum entries → TP/SL/time exits → [[Scalper Live]] (went live 2026-07-02; first session: 3 entries, 1 take-profit +8.37%). Run all the time: double-click `market/scalper.bat`.

## Planned Automations

- [ ] Token watchlist prices for the [[Risk Agent]] (DexScreener / Birdeye APIs)
- [ ] Alert thresholds on the [[Solana Live Feed]] for the [[Monitoring Agent]]
- [ ] Weekly lessons review trigger for the [[Learning Agent]]
- [ ] Report pipeline: agent Reports → [[Home]] dashboard summary

## Rules

- Automations execute through the [[Execution Agent]] rules — approved plans only
- Every automation gets a note here before it goes live
