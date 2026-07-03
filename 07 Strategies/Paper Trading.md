---
tags: [strategy, paper-trading, live]
updated: 2026-07-02 23:38:07 UTC
---

# 🧪 Paper Trading

Hypothetical trades executed at **real live prices** — Stage 3 of the [[AI Solana System]] roadmap. This is where the [[Strategy Agent]]'s ideas are tested and the [[Learning Agent]] compares predictions with outcomes. **No real funds are ever used here.**

← [[Home]] · Prices: [[Market Watch]] · Rules: [[Trading#Risk Management|Trading risk rules]]

## 📈 Scoreboard

| Closed trades | Win rate | Total P&L (paper) |
|---|---|---|
| 2 | 50% | 🟢 +$2.09 |

## 🔓 Open Positions

| ID | Token | Size | Entry | Opened | Reasoning |
|---|---|---|---|---|---|
| #1 | **SOL** | $100 | $80.42 | 2026-07-02 23:15:56 UTC | Test position: price above 2-day average, uptrend per Training Log; liquidity deep at 25M |
| #4 | **BULLWIF** | $25 | $0.0002068 | 2026-07-02 23:36:42 UTC | [SCALPER] momentum: m5 +2.969%, h1 +25.672%, vol1h $11k, buys/sells 14/2; risk 0/10 pass |
| #5 | **FROGBULL** | $25 | $0.0005791 | 2026-07-02 23:36:43 UTC | [SCALPER] momentum: m5 +4.867%, h1 +42.474%, vol1h $19k, buys/sells 15/9; risk 0/10 pass |

## 📕 Closed Trades

| ID | Token | Size | Entry | Exit | P&L | Reasoning |
|---|---|---|---|---|---|---|
| #3 | **LojakPaul** | $25 | $0.001875 | $0.002032 | 🟢 +$2.09 (+8.37%) | [SCALPER] momentum: m5 +2.022%, h1 +19.893%, vol1h $180k, buys/sells 23/10; risk 1/10 pass → take-profit +8% hit |
| #2 | **WIF** | $25 | $0.1723 | $0.1723 | 🟢 +$0.00 (+0.00%) | Full-cycle test trade to verify P&L math → closing immediately - cycle verification only |

## How to trade (paper)

```
node "09 Automation/market/paper-trade.mjs" open SOL 100 "reason for entry"
node "09 Automation/market/paper-trade.mjs" close 1 "reason for exit"
node "09 Automation/market/paper-trade.mjs" status
```

## The gate to real execution

Per the roadmap, the [[Execution Agent]] stays on standby until this log shows **consistent performance** — reviewed by the [[Learning Agent]] and [[Risk Agent]]. Only then does Stage 5 (small live execution) begin.

## Related

- [[Market Watch]] · [[Strategy Hub]] · [[Training Log]] · [[Agent Control Center]]
