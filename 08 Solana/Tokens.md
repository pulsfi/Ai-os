---
tags: [solana, tokens, crypto]
created: 2026-07-02
---

# Tokens

Everything that lives on [[Solana]] as a tradeable asset. Tokens on Solana follow the **SPL (Solana Program Library)** standard — the equivalent of ERC-20 on Ethereum.

## SOL

The native token of the Solana network.

- **Uses:** paying transaction fees, staking with validators, governance, and as the base trading pair for most Solana [[Trading]]
- **Units:** 1 SOL = 1,000,000,000 lamports (the smallest unit)
- Always keep a small SOL balance in your [[Wallet]] for fees and rent

## Categories of SPL Tokens

### Stablecoins
Pegged to fiat currency, used for parking value and pricing trades.
- **USDC** — the dominant stablecoin on Solana
- **USDT** — Tether, also widely available

### DeFi / Utility Tokens
Tokens tied to protocols:
- **JUP** — Jupiter (DEX aggregator)
- **RAY** — Raydium
- **JTO** — Jito (liquid staking / MEV)

### Liquid Staking Tokens (LSTs)
Represent staked SOL that stays liquid:
- **mSOL** (Marinade), **jitoSOL** (Jito), **bSOL** (BlazeStake)
- Earn staking yield while remaining tradeable

### Memecoins
Community/speculation-driven tokens with no intrinsic utility:
- Examples that got large: BONK, WIF (dogwifhat)
- Thousands launch daily via Pump.fun — **the vast majority go to zero**
- Extremely high risk; see the risk rules in [[Trading]]

## Token Safety Checklist

Before buying any small-cap token:

- [ ] Check liquidity amount and whether LP is locked/burned
- [ ] Check holder distribution (is one wallet holding 50%?)
- [ ] Verify mint authority is revoked (otherwise supply can be inflated)
- [ ] Verify freeze authority is revoked (otherwise your tokens can be frozen)
- [ ] Run it through rugcheck.xyz
- [ ] Search the contract address on DEX Screener for history

## Key Terms

| Term | Meaning |
|---|---|
| Mint address | The unique contract address identifying a token |
| Supply | Total number of tokens in existence |
| ATA | Associated Token Account — the account in your wallet that holds a specific token |
| Airdrop | Free token distribution (also a common scam vector — see [[Wallet]] security rules) |

## Related

- [[Solana]] — the network these tokens live on
- [[Wallet]] — where tokens are stored
- [[Trading]] — how to buy and sell them
- [[Solana Hub]] — the knowledge base this note belongs to
- [[Risk Agent]] — enforces the safety checklist above
