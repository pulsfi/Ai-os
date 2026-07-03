---
tags: [automation, market, live]
created: 2026-07-02
status: live
---

# 📊 Market Data Service

Stage 3 infrastructure of the [[AI Solana System]] — a multi-source market data pipeline. **It downloads data and stores it; it does not place trades.**

## Architecture

```
Live APIs (CoinGecko · DexScreener · Jupiter · RPC · Birdeye*)
     │
     ▼  market-manager.mjs
Market Database (SQLite: market.db)
     │
     ├── [[Research Agent]]   — summarizes market activity
     ├── [[Risk Agent]]       — acts on liquidity/move/divergence flags
     ├── [[Strategy Agent]]   — proposes ideas → [[Paper Trading]]
     └── [[Monitoring Agent]] — watches outages & anomalies
```
*Birdeye needs a free API key; the other four run keyless.

## 🔑 API keys — one file

All keys and settings live in **`09 Automation/.env`** (every value optional; the system runs on free public endpoints when empty):

| Variable | What it unlocks |
|---|---|
| `HELIUS_API_KEY` | Fast, reliable RPC (free at helius.dev) — recommended first upgrade per the [[04 Agents/Research Agent/Reports\|Helius report]] |
| `SOLANA_RPC_URL` | Or paste any full RPC URL (QuickNode etc.) instead |
| `BIRDEYE_API_KEY` | Birdeye as a 4th price source |
| `COINGECKO_API_KEY` / `JUPITER_API_KEY` | Pro tiers (free tiers need none) |
| `WALLET_ADDRESS` | Live balance in [[Solana Live]] — **public address only, never a seed phrase** (see [[Wallet#Security Rules\|Wallet Security Rules]]) |
| `ALERT_THRESHOLD` | % move that triggers a 🔴 alert (default 10) |

All scripts (live feed, daily cycle, market manager, paper trading) read it automatically via `lib/env.mjs`.

## Files (`09 Automation/market/`)

| File | Job |
|---|---|
| `sources/rpc.mjs` | Solana chain status (Helius/QuickNode-ready) |
| `sources/coingecko.mjs` | General crypto prices |
| `sources/dexscreener.mjs` | DEX pairs — price, liquidity, volume (major-quote pairs only) |
| `sources/jupiter.mjs` | Price cross-check + swap route quotes |
| `sources/birdeye.mjs` | Token prices (optional, keyed) |
| `market-manager.mjs` | Orchestrator: fetch all → save snapshots → write [[Market Watch]] |
| `paper-trade.mjs` | Paper trading engine → writes [[Paper Trading]] |
| `db.mjs` + `market.db` | SQLite: `snapshots` + `paper_trades` tables |
| `watchlist.json` | Tokens to track (symbol, mint, CoinGecko id) |

## Data integrity (learned live on day one)

- **Cross-source divergence check** — every run compares CoinGecko vs DexScreener vs Jupiter; >2% disagreement raises a ⚠️ flag. On the very first live run this caught a bad DexScreener pool (JUP/JTO reporting $1,237 instead of $0.24) — the fix: only major-quote pairs (SOL/USDC/USDT) are trusted.
- Snapshots only save when at least one source returns a price.

## Run it

```
node "09 Automation/market/market-manager.mjs"        # one snapshot cycle (~1.3s)
node "09 Automation/market/paper-trade.mjs" status    # paper portfolio
```

Add tokens by editing `watchlist.json` (symbol + mint + CoinGecko id).

## Related

- [[Market Watch]] — the live output dashboard
- [[Paper Trading]] — Stage 3 testing ground
- [[Solana Live Feed]] · [[Training Log]] · [[Automation Hub]]
