---
tags: [automation, solana, live]
created: 2026-07-02
status: live
---

# 📡 Solana Live Feed

First automation of the [[Automation Hub]] — connects the vault to the **live Solana mainnet**. It fetches real chain data and rewrites [[Solana Live]] on every run, on behalf of the [[Monitoring Agent]].

## What it pulls

| Data | Source | Feeds |
|---|---|---|
| SOL price, 24h change, market cap | CoinGecko public API | [[Trading]], [[Strategy Agent]] |
| Slot, block height, epoch progress | Solana mainnet RPC | [[Solana]] |
| TPS (recent average) | RPC performance samples | [[Solana]] |
| Active / delinquent validators | RPC vote accounts | [[Solana]] |
| Wallet SOL balance *(optional)* | RPC `getBalance` | [[Wallet]], [[Monitoring Agent]] |

No API keys needed — all public endpoints.

## Files

All in `09 Automation/scripts/`:

- `solana-live.mjs` — the feed script (Node.js, zero dependencies)
- `../.env` — all API keys & settings in one place (public wallet address only — **never** a seed phrase, per [[Wallet#Security Rules|Wallet Security Rules]])
- `refresh.bat` — double-click to refresh once

## How to run

- **Once:** double-click `refresh.bat`, or `node solana-live.mjs`
- **Continuous (live mode):** `node solana-live.mjs --loop 60` — refreshes every 60 s while running
- **Automatic on a schedule:** create a Windows Task Scheduler job (runs every 15 min even when Obsidian is closed):

```
schtasks /Create /TN "SolanaLiveFeed" /SC MINUTE /MO 15 ^
  /TR "\"C:\Users\Tahfeez\OneDrive\Desktop\OS AI\OS AI\09 Automation\scripts\refresh.bat\"" /F
```

Remove it anytime with `schtasks /Delete /TN "SolanaLiveFeed" /F`.

## Upgrade path

- Swap `rpcUrl` in `config.json` for a **Helius** endpoint for faster, more reliable data — see the [[04 Agents/Research Agent/Reports|Helius RPC research report]]
- Add token watchlist prices for the [[Risk Agent]]
- Add alert thresholds (price moves, wallet changes) → alerts logged to [[04 Agents/Monitoring Agent/Reports|Monitoring Reports]]

## Related

- [[Solana Live]] — the output dashboard
- [[Monitoring Agent]] — owner of this feed
- [[Automation Hub]] · [[Home]]
