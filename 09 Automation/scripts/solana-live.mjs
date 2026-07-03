#!/usr/bin/env node
/**
 * Solana Live Feed — pulls real-time data from Solana mainnet and writes it
 * into the vault as "00 Dashboard/Solana Live.md".
 *
 * Data sources (no API keys needed):
 *   - Solana public RPC  : slot, epoch, block height, TPS, validators, health
 *   - CoinGecko public API: SOL price + 24h change
 *   - Optional: wallet SOL balance (set walletAddress in config.json)
 *
 * Usage:
 *   node solana-live.mjs           # refresh once
 *   node solana-live.mjs --loop 60 # refresh every 60 seconds (Ctrl+C to stop)
 */

import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { CONFIG } from "../lib/env.mjs";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const VAULT_ROOT = join(SCRIPT_DIR, "..", "..");
const OUT_NOTE = join(VAULT_ROOT, "00 Dashboard", "Solana Live.md");

const RPC_URL = CONFIG.rpcUrl;
const WALLET = CONFIG.walletAddress;

async function rpc(method, params = []) {
  const res = await fetch(RPC_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const json = await res.json();
  if (json.error) throw new Error(`${method}: ${json.error.message}`);
  return json.result;
}

async function safe(label, fn) {
  try {
    return await fn();
  } catch (err) {
    console.error(`  ! ${label} failed: ${err.message}`);
    return null;
  }
}

async function fetchAll() {
  const [health, slot, epoch, blockHeight, perf, votes, price, balance] =
    await Promise.all([
      safe("health", () => rpc("getHealth")),
      safe("slot", () => rpc("getSlot")),
      safe("epoch", () => rpc("getEpochInfo")),
      safe("blockHeight", () => rpc("getBlockHeight")),
      safe("performance", () => rpc("getRecentPerformanceSamples", [5])),
      safe("validators", () => rpc("getVoteAccounts")),
      safe("price", async () => {
        const res = await fetch(
          "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true&include_market_cap=true",
        );
        return (await res.json()).solana;
      }),
      WALLET
        ? safe("wallet balance", () => rpc("getBalance", [WALLET]))
        : Promise.resolve(null),
    ]);

  let tps = null;
  if (perf?.length) {
    const totalTx = perf.reduce((s, p) => s + p.numTransactions, 0);
    const totalSecs = perf.reduce((s, p) => s + p.samplePeriodSecs, 0);
    if (totalSecs > 0) tps = Math.round(totalTx / totalSecs);
  }

  return { health, slot, epoch, blockHeight, tps, votes, price, balance };
}

const fmt = (n) => (n == null ? "—" : n.toLocaleString("en-US"));

function buildNote(d) {
  const now = new Date();
  const stamp = now.toISOString().replace("T", " ").slice(0, 19) + " UTC";
  const ok = d.health === "ok";
  const statusEmoji = ok ? "🟢" : d.health == null ? "⚪" : "🔴";
  const statusText = ok ? "Healthy" : d.health == null ? "Unreachable" : "Degraded";

  const epochPct = d.epoch
    ? ((d.epoch.slotIndex / d.epoch.slotsInEpoch) * 100).toFixed(1)
    : null;
  const activeValidators = d.votes ? d.votes.current.length : null;
  const delinquent = d.votes ? d.votes.delinquent.length : null;

  const priceUsd = d.price?.usd != null ? `$${d.price.usd.toLocaleString("en-US")}` : "—";
  const change = d.price?.usd_24h_change;
  const changeStr =
    change == null
      ? "—"
      : `${change >= 0 ? "📈 +" : "📉 "}${change.toFixed(2)}%`;
  const mcap =
    d.price?.usd_market_cap != null
      ? `$${(d.price.usd_market_cap / 1e9).toFixed(1)}B`
      : "—";

  const walletSection = WALLET
    ? `
## 👛 Wallet

| Address | SOL Balance |
|---|---|
| \`${WALLET.slice(0, 4)}…${WALLET.slice(-4)}\` | ${
        d.balance ? (d.balance.value / 1e9).toLocaleString("en-US") : "—"
      } SOL |

Watched by the [[Monitoring Agent]] — security rules in [[Wallet]].
`
    : `
## 👛 Wallet

No wallet configured. Add your public address to \`09 Automation/scripts/config.json\` (\`walletAddress\`) to track the [[Wallet]] balance live.
`;

  return `---
tags: [live, solana, dashboard]
updated: ${stamp}
---

# 📡 Solana Live

${statusEmoji} **Mainnet: ${statusText}** · Last refresh: **${stamp}**

← Back to [[Home]] · Owned by the [[Monitoring Agent]] · Feed docs: [[Solana Live Feed]]

## 💰 SOL Market

| Price | 24h Change | Market Cap |
|---|---|---|
| **${priceUsd}** | ${changeStr} | ${mcap} |

Price context for [[Trading]] and the [[Strategy Agent]].

## ⛓️ Network

| Metric | Value |
|---|---|
| Current slot | ${fmt(d.slot)} |
| Block height | ${fmt(d.blockHeight)} |
| Epoch | ${d.epoch ? `${d.epoch.epoch} (${epochPct}% complete)` : "—"} |
| TPS (recent avg) | ${fmt(d.tps)} |
| Active validators | ${fmt(activeValidators)} |
| Delinquent validators | ${fmt(delinquent)} |

Network concepts explained in [[Solana]].
${walletSection}
## 🔄 How this updates

Run \`refresh.bat\` in \`09 Automation/scripts\` (or \`node solana-live.mjs --loop 60\` for continuous updates). Setup + scheduling: [[Solana Live Feed]].

## Related

- [[Solana Hub]] — the knowledge base
- [[Monitoring Agent]] — owns this feed
- [[Automation Hub]] — all automations
`;
}

async function refresh() {
  console.log(`→ Fetching live Solana data from ${RPC_URL} ...`);
  const data = await fetchAll();
  writeFileSync(OUT_NOTE, buildNote(data), "utf8");
  console.log(
    `✓ ${new Date().toLocaleTimeString()} — slot ${fmt(data.slot)}, ` +
      `TPS ${fmt(data.tps)}, SOL ${data.price?.usd != null ? "$" + data.price.usd : "—"} → Solana Live.md`,
  );
}

const loopIdx = process.argv.indexOf("--loop");
if (loopIdx !== -1) {
  const secs = Math.max(10, Number(process.argv[loopIdx + 1]) || 60);
  console.log(`Live mode: refreshing every ${secs}s. Ctrl+C to stop.`);
  await refresh();
  setInterval(() => refresh().catch((e) => console.error(e.message)), secs * 1000);
} else {
  await refresh();
}
