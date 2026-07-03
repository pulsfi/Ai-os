---
tags: [strategy, scalper, live, paper-trading]
updated: 2026-07-02 23:38:07 UTC
---

# ⚡ Scalper Live (Paper Mode)

Autonomous meme coin scalper — scans trending [[Solana]] pools, risk-checks every token through the **Stage 4 Risk Engine**, and takes quick momentum scalps **on paper at real live prices**. Strategy of the [[Strategy Agent]], safety by the [[Risk Agent]], results reviewed by the [[Learning Agent]].

← [[Home]] · Full trade DB: [[Paper Trading]] · Radar: GeckoTerminal trending

## ⚙️ Strategy Settings (edit in `09 Automation/.env`)

| Size/trade | Max open | Take profit | Stop loss | Time stop | Min liquidity | Min pool age | Cooldown |
|---|---|---|---|---|---|---|---|
| $25 | 3 | +8% | −5% | 45 min | $50,000 | 1h | 60 min |

## 📈 Scalp Scoreboard

| Closed scalps | Wins | Total P&L (paper) |
|---|---|---|
| 1 | 1 | 🟢 +$2.09 |

## 🔓 Open Scalps

| ID | Token | Size | Entry | Opened |
|---|---|---|---|---|
| #4 | **BULLWIF** | $25 | $0.0002068 | 2026-07-02 23:36:42 UTC |
| #5 | **FROGBULL** | $25 | $0.0005791 | 2026-07-02 23:36:43 UTC |

## 📕 Recent Closed Scalps

| ID | Token | Entry → Exit | P&L | Exit reason |
|---|---|---|---|---|
| #3 | **LojakPaul** | $0.001875 → $0.002032 | 🟢 +$2.09 (+8.37%) | take-profit +8% hit |

## 🖥️ Last Cycle — 2026-07-02 23:38:07 UTC

```
📕 CLOSE #3 LojakPaul: $0.001875 → $0.002032 = +8.37% (take-profit +8% hit)
⏳ HOLD #4 BULLWIF: +0.24% after 1min
⏳ HOLD #5 FROGBULL: +0.45% after 1min
📡 scanned 20 trending pools → 2 momentum candidate(s)
🕐 LojakPaul: cooldown — skipped
```

## ⛔ The Stage 5 gate

This bot trades **paper money at real prices**. Live execution stays locked until the scoreboard proves consistent profit over a real track record — reviewed by the [[Learning Agent]], enforced by the [[Risk Agent]], per the [[AI Solana System]] roadmap.

## Related

- [[Paper Trading]] · [[Market Watch]] · [[Market Data Service]] · [[Agent Control Center]]
