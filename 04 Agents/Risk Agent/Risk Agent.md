---
tags: [agent, risk, security]
status: active
created: 2026-07-02
---

# 🛡️ Risk Agent

Protects the system. Detects scams, scores every opportunity, and blocks bad decisions before they reach the [[Execution Agent]]. The safety gate of the [[Agent Control Center]] pipeline.

| File | Purpose |
|---|---|
| [[04 Agents/Risk Agent/Mission\|Mission]] | Why this agent exists |
| [[04 Agents/Risk Agent/Rules\|Rules]] | How it behaves |
| [[04 Agents/Risk Agent/Tasks\|Tasks]] | Current work queue |
| [[04 Agents/Risk Agent/Memory\|Memory]] | What it has learned |
| [[04 Agents/Risk Agent/Reports\|Reports]] | Output it has produced |

**Enforces:** [[Tokens#Token Safety Checklist|Token Safety Checklist]] and [[Wallet#Security Rules|Wallet Security Rules]]
**Feeds risk scores to:** [[Strategy Agent]]

> [!success] Risk Engine automated (Stage 4)
> This agent's checklist now runs as code: `09 Automation/market/risk-engine.mjs` scores every token on-chain (mint/freeze authority, liquidity, holder concentration, pool age) and **gates every [[Scalper Live]] entry** — ⛔ block is final.
