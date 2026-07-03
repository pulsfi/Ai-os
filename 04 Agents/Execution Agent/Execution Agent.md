---
tags: [agent, execution]
status: standby
created: 2026-07-02
---

# ⚡ Execution Agent

Carries out **approved plans only** — swaps via [[Trading]], transfers via [[Wallet]]. Never decides anything itself. Last action stage of the [[Agent Control Center]] pipeline.

| File | Purpose |
|---|---|
| [[04 Agents/Execution Agent/Mission\|Mission]] | Why this agent exists |
| [[04 Agents/Execution Agent/Rules\|Rules]] | How it behaves |
| [[04 Agents/Execution Agent/Tasks\|Tasks]] | Current work queue |
| [[04 Agents/Execution Agent/Memory\|Memory]] | What it has learned |
| [[04 Agents/Execution Agent/Reports\|Reports]] | Output it has produced |

**Receives approved plans from:** [[Strategy Agent]] · **Results reviewed by:** [[Learning Agent]]

> [!warning]
> This agent only acts on plans that passed the [[Risk Agent]]. No exceptions.
