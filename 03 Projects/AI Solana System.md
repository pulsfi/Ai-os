---
tags: [project, active]
created: 2026-07-02
---

# 🚀 AI Solana System

← Back to [[Home]] · Template: [[Project Template]]

## Goal

Build an autonomous AI system using Claude and [[Solana]] — a team of agents that researches, plans, checks risk, executes, and learns.

## Status

🟢 **Active** — vault built and fully connected; agents defined and live in the [[Agent Control Center]].

## Architecture

The system is the pipeline described in the [[Agent Control Center]]:

> [[Research Agent]] → [[Documentation Agent]] → [[Risk Agent]] → [[Strategy Agent]] → [[Execution Agent]] → [[Learning Agent]] → back to memory

- **Knowledge layer:** [[Knowledge Hub]] + [[Solana Hub]]
- **Memory layer:** [[Memory Hub]]
- **Live layer:** [[Monitoring Agent]] watching [[Wallet]], [[Tokens]], [[Trading]]
- **Automation layer:** [[Automation Hub]]

## Roadmap — The Six Stages

| Stage | What | Status |
|---|---|---|
| 1 | AI OS (Obsidian + Claude) | ✅ Done 2026-07-02 |
| 2 | Live Market Data — [[Solana Live Feed]], [[Market Data Service]], SQLite history | ✅ Done 2026-07-02 |
| 3 | [[Paper Trading]] — hypothetical trades at real prices, P&L tracked | 🟢 **Running — [[Scalper Live]] trades autonomously** |
| 4 | Risk Engine — on-chain mint/freeze/liquidity/holder checks gate every entry | ✅ Done 2026-07-02 — `market/risk-engine.mjs` |
| 5 | Small Live Execution — only after the scalper's paper track record proves out | ⚪ Gated |
| 6 | Multi-Agent Automation — full pipeline hands-free | 🟡 Started — scalper loop = radar + risk + strategy + learning in one cycle |

**The separation that keeps it safe:**
Market Data → Research → Risk Review → Strategy Proposal → Paper Trade → Performance Review → *(only then)* Execution

- [x] Build the vault structure (2026-07-02)
- [x] Define all 7 agents with missions, rules, tasks, memory, reports
- [x] Connect every note in the graph
- [x] Live feeds + daily self-training ([[Training Log]])
- [x] Market database + paper trading engine (2026-07-02)
- [ ] First research cycle — RPC + wallet comparison ([[04 Agents/Research Agent/Tasks|Research Tasks]])
- [ ] First strategy draft in the [[Strategy Hub]] → tested in [[Paper Trading]]
- [ ] 30 days of paper trading track record before any live execution

## Tasks

Current work is tracked per agent — see the [[Agent Control Center]] status board.

## Risks

- Memecoin exposure — mitigated by the [[Risk Agent]] and the [[Tokens#Token Safety Checklist|Token Safety Checklist]]
- Key security — governed by [[Wallet#Security Rules|Wallet Security Rules]]
- Over-automation — the [[Execution Agent]] only ever runs approved plans

## Ideas

- Staking / LST yield strategy (see [[Tokens]])
- On-chain alert bot for the [[Monitoring Agent]]

## Research & Reports

- Findings: [[Research Hub]] · First report: [[04 Agents/Research Agent/Reports|Helius RPC]]

## Resources

- solana.com · solscan.io · docs.solana.com (full list in [[Solana]])
