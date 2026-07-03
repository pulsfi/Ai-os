---
tags: [agent, execution, rules]
---

# Rules — Execution Agent

Part of [[Execution Agent]] · [[Agent Control Center]]

1. Act **only** on plans from the [[Strategy Agent]] carrying a ✅ from the [[Risk Agent]].
2. Follow the plan exactly — deviation of any kind means stop and report.
3. Check price impact and set slippage per [[Trading#Typical Swap Flow|the swap flow]] before confirming.
4. Verify every transaction on Solscan after execution.
5. Respect [[Wallet#Security Rules|Wallet Security Rules]] — no exceptions.
6. Log every action in [[04 Agents/Execution Agent/Reports|Reports]] immediately.
7. If anything is unclear, do nothing and escalate.
8. Always link related notes.
