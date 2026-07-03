---
tags: [live, market, dashboard]
updated: 2026-07-02 23:29:17 UTC
---

# 📊 Market Watch

Live multi-source market data for the watchlist. Written by the **Market Manager** (`09 Automation/market/`) — Stage 3 of the [[AI Solana System]] roadmap. It downloads data and saves snapshots; **it does not place trades**.

← [[Home]] · Chain: 🟢 slot 430,404,887, TPS 3199 · DB: **14 snapshots / 1 days**

## Watchlist

| Token | Price | 24h | Volume 24h | Liquidity | Mkt Cap | Sources |
|---|---|---|---|---|---|---|
| **SOL** | $80.60 | +3.86% | $156.7M | $25.3M | $46.8B | coingecko+dexscreener+jupiter |
| **JUP** | $0.2437 | +4.02% | $1.9M | $1.0M | $807.4M | coingecko+dexscreener+jupiter |
| **BONK** | $0.000004342 | +1.56% | $8,088 | $249,946 | $381.5M | coingecko+dexscreener+jupiter |
| **WIF** | $0.1728 | +2.49% | $438,900 | $4.6M | $172.2M | coingecko+dexscreener+jupiter |

## 🚩 Flags for the Agents

- ✅ No risk flags on the current watchlist.

## Agent Pipeline (Step 4)

- [[Research Agent]] — summarizes market activity from these snapshots
- [[Risk Agent]] — acts on the flags above (liquidity, moves, divergence)
- [[Strategy Agent]] — proposes ideas → tested first in [[Paper Trading]]
- [[Monitoring Agent]] — watches for outages and anomalies

## Related

- [[Paper Trading]] — hypothetical trades against these live prices
- [[Solana Live]] · [[Training Log]] · [[Market Data Service]]
