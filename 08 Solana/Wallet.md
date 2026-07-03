---
tags: [solana, wallet, security]
created: 2026-07-02
---

# Wallet

A wallet stores the **private keys** that control your funds on [[Solana]]. The wallet doesn't hold coins itself — it holds the keys that prove ownership of addresses on the blockchain.

## Types of Wallets

### Hot Wallets (connected to the internet)
- **Phantom** — the most popular Solana wallet; browser extension + mobile app
- **Solflare** — feature-rich, good staking support
- **Backpack** — supports xNFTs and integrates with the Backpack exchange

### Cold Wallets (offline, most secure)
- **Ledger** — hardware wallet, works with Phantom/Solflare as an interface
- Best for long-term holdings and larger amounts

## Key Concepts

| Term | Meaning |
|---|---|
| Seed phrase | 12–24 words that can restore your entire wallet. **Never share it.** |
| Private key | The secret that signs transactions |
| Public key / Address | Your shareable receiving address (base58 string) |
| Rent | Small SOL amount locked to keep accounts open on Solana |

## Security Rules

> [!warning] Golden Rules
> 1. **Never** type your seed phrase into a website — no legitimate service ever asks for it.
> 2. Write the seed phrase on paper (or metal); don't store it in screenshots, cloud notes, or email.
> 3. Verify URLs — phishing sites mimic Phantom, Jupiter, etc.
> 4. Revoke old token approvals periodically.
> 5. Use a **burner wallet** for minting/interacting with unknown dApps; keep main funds separate.
> 6. Beware of random tokens/NFTs airdropped to you — they're often scam bait. Don't interact with them.

## Setup Checklist

- [ ] Install Phantom (or Solflare) from the official site
- [ ] Create a wallet and back up the seed phrase offline
- [ ] Send a small test amount of SOL first
- [ ] Keep some SOL for fees and rent (~0.05 SOL minimum)
- [ ] Consider a hardware wallet for anything substantial

## Related

- [[Solana]] — the network itself
- [[Trading]] — connecting your wallet to DEXs
- [[Tokens]] — what your wallet will hold
- [[Solana Hub]] — the knowledge base this note belongs to
- [[Risk Agent]] — enforces the security rules above
