---
tags: [solana, trading, defi]
created: 2026-07-02
---

# Trading

Buying, selling, and swapping [[Tokens]] on [[Solana]]. There are two main venues: centralized exchanges (CEXs) and decentralized exchanges (DEXs).

## Where to Trade

### Centralized Exchanges (CEX)
Custodial platforms — they hold your funds; you trade through their interface.
- Examples: Binance, Coinbase, Kraken, Bybit
- Good for: fiat on/off ramps, buying SOL with a card or bank transfer
- Risk: you don't control the keys ("not your keys, not your coins")

### Decentralized Exchanges (DEX)
Non-custodial — you trade directly from your [[Wallet]].
- **Jupiter (jup.ag)** — aggregator that finds the best price across all Solana DEXs; the default choice for swaps
- **Raydium** — AMM with deep liquidity; where many new tokens launch
- **Orca** — user-friendly AMM
- **Pump.fun** — memecoin launchpad (extremely high risk)

## Key Concepts

| Term | Meaning |
|---|---|
| Swap | Exchanging one token for another |
| Slippage | Price movement between placing and executing a trade |
| Liquidity | How much of a token is available to trade; low liquidity = big price impact |
| Market cap | Token price × circulating supply |
| Limit order | Order that executes only at your chosen price |
| DCA | Dollar-cost averaging — buying fixed amounts on a schedule |

## Typical Swap Flow

1. Fund your [[Wallet]] with SOL
2. Go to Jupiter → connect wallet
3. Choose the pair (e.g., SOL → USDC)
4. Check **price impact** and set slippage (0.5–1% for majors, higher for volatile tokens)
5. Confirm the transaction in your wallet
6. Verify on Solscan

## Risk Management

> [!warning] Rules to survive
> - Only trade what you can afford to lose — Solana memecoins can go to zero in minutes.
> - Check token liquidity and whether it's locked before buying small caps.
> - Watch for **honeypots** (tokens you can buy but not sell) — use rugcheck.xyz.
> - Take profits on the way up; don't round-trip gains.
> - Keep records for taxes.
> - Avoid FOMO entries into vertical charts.

## Useful Tools

- **DEX Screener / Birdeye** — charts and token data
- **Solscan** — transaction explorer
- **RugCheck** — token safety checks

## Related

- [[Solana]] — network overview
- [[Wallet]] — set this up first
- [[Tokens]] — know what you're trading
- [[Solana Hub]] — the knowledge base this note belongs to
- [[Execution Agent]] — follows the swap flow above
- [[Strategy Agent]] — plans within the risk rules above
