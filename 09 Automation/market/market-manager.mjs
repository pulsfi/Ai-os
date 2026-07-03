#!/usr/bin/env node
/**
 * Market Manager — Stage 3, Steps 1-4 of the roadmap.
 *
 * Downloads current prices, volume, liquidity from all sources,
 * saves snapshots to the SQLite database, and writes the agent-facing
 * note "00 Dashboard/Market Watch.md" with auto-generated flags for the
 * Research / Risk / Strategy / Monitoring agents.
 *
 * It does NOT place trades.
 *
 * Usage:  node market-manager.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { CONFIG } from "../lib/env.mjs";
import { chainStatus } from "./sources/rpc.mjs";
import { cgPrices } from "./sources/coingecko.mjs";
import { dsToken } from "./sources/dexscreener.mjs";
import { jupPrices } from "./sources/jupiter.mjs";
import { bePrice } from "./sources/birdeye.mjs";
import { openDb, insertSnapshot, dbStats } from "./db.mjs";

const DIR = dirname(fileURLToPath(import.meta.url));
const VAULT = join(DIR, "..", "..");
const OUT = join(VAULT, "00 Dashboard", "Market Watch.md");
const CFG = CONFIG;
const RPC_URL = CONFIG.rpcUrl;

const watchlist = JSON.parse(readFileSync(join(DIR, "watchlist.json"), "utf8"));
const t0 = Date.now();
console.log(`→ Market Manager: ${watchlist.length} tokens, 5 sources...`);

const safe = (p) => p.catch((e) => (console.error(`  ! ${e.message}`), null));

// ---- Step 1-2: download from all sources in parallel ----
const [cg, jup, chain, ...ds] = await Promise.all([
  safe(cgPrices(watchlist.map((w) => w.coingeckoId))),
  safe(jupPrices(watchlist.map((w) => w.mint))),
  safe(chainStatus(RPC_URL)),
  ...watchlist.map((w) => safe(dsToken(w.mint))),
]);
const be = await Promise.all(
  watchlist.map((w) => safe(Promise.resolve(bePrice(w.mint, CFG.birdeyeApiKey)))),
);

// ---- merge per token ----
const ts = new Date().toISOString();
const tokens = watchlist.map((w, i) => {
  const g = cg?.[w.coingeckoId];
  const d = ds[i];
  const j = jup?.[w.mint];
  const b = be[i];
  const sources = [g && "coingecko", d && "dexscreener", j != null && "jupiter", b != null && "birdeye"]
    .filter(Boolean)
    .join("+");
  const price = d?.priceUsd ?? g?.usd ?? j ?? b ?? null;
  // cross-source divergence check (data integrity)
  const prices = [d?.priceUsd, g?.usd, j, b].filter((p) => p != null);
  const divergence =
    prices.length >= 2
      ? +(((Math.max(...prices) - Math.min(...prices)) / Math.min(...prices)) * 100).toFixed(2)
      : null;
  return {
    ts,
    symbol: w.symbol,
    mint: w.mint,
    price,
    change24h: d?.change24h ?? g?.usd_24h_change ?? null,
    volume24h: d?.volume24h ?? g?.usd_24h_vol ?? null,
    liquidity: d?.liquidityUsd ?? null,
    marketCap: g?.usd_market_cap ?? d?.fdv ?? null,
    sources,
    divergence,
    dex: d?.dex ?? null,
  };
});

// ---- Step 3: save snapshots to the database ----
const db = openDb();
for (const t of tokens) if (t.price != null) insertSnapshot(db, t);
const stats = dbStats(db);

// ---- Step 4: agent-facing flags ----
const flags = [];
for (const t of tokens) {
  if (t.price == null) flags.push(`🔴 **${t.symbol}** — no price from any source → [[Monitoring Agent]] check feeds`);
  if (t.liquidity != null && t.liquidity < 100_000)
    flags.push(`🔴 **${t.symbol}** — liquidity $${Math.round(t.liquidity).toLocaleString()} < $100k → [[Risk Agent]] block`);
  if (t.change24h != null && Math.abs(t.change24h) >= 20)
    flags.push(`⚠️ **${t.symbol}** — moved ${t.change24h.toFixed(1)}% in 24h → [[Risk Agent]] review`);
  if (t.divergence != null && t.divergence > 2)
    flags.push(`⚠️ **${t.symbol}** — sources disagree by ${t.divergence}% → [[Monitoring Agent]] verify`);
}
if (!flags.length) flags.push("✅ No risk flags on the current watchlist.");

// ---- write the vault note ----
const money = (n) =>
  n == null ? "—" : n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : `$${Math.round(n).toLocaleString()}`;
const px = (n) => (n == null ? "—" : n >= 1 ? `$${n.toFixed(2)}` : `$${n.toPrecision(4)}`);
const pct = (n) => (n == null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`);

const rows = tokens
  .map(
    (t) =>
      `| **${t.symbol}** | ${px(t.price)} | ${pct(t.change24h)} | ${money(t.volume24h)} | ${money(t.liquidity)} | ${money(t.marketCap)} | ${t.sources || "—"} |`,
  )
  .join("\n");

writeFileSync(
  OUT,
  `---
tags: [live, market, dashboard]
updated: ${ts.replace("T", " ").slice(0, 19)} UTC
---

# 📊 Market Watch

Live multi-source market data for the watchlist. Written by the **Market Manager** (\`09 Automation/market/\`) — Stage 3 of the [[AI Solana System]] roadmap. It downloads data and saves snapshots; **it does not place trades**.

← [[Home]] · Chain: ${chain?.health === "ok" ? "🟢" : "🔴"} slot ${chain?.slot?.toLocaleString() ?? "—"}, TPS ${chain?.tps ?? "—"} · DB: **${stats.snapshots} snapshots / ${stats.days} days**

## Watchlist

| Token | Price | 24h | Volume 24h | Liquidity | Mkt Cap | Sources |
|---|---|---|---|---|---|---|
${rows}

## 🚩 Flags for the Agents

${flags.map((f) => `- ${f}`).join("\n")}

## Agent Pipeline (Step 4)

- [[Research Agent]] — summarizes market activity from these snapshots
- [[Risk Agent]] — acts on the flags above (liquidity, moves, divergence)
- [[Strategy Agent]] — proposes ideas → tested first in [[Paper Trading]]
- [[Monitoring Agent]] — watches for outages and anomalies

## Related

- [[Paper Trading]] — hypothetical trades against these live prices
- [[Solana Live]] · [[Training Log]] · [[Market Data Service]]
`,
  "utf8",
);

console.log(`✓ ${tokens.filter((t) => t.price != null).length}/${tokens.length} tokens priced in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
for (const t of tokens)
  console.log(
    `  ${t.symbol.padEnd(5)} ${px(t.price).padEnd(10)} 24h ${pct(t.change24h).padEnd(8)} liq ${money(t.liquidity).padEnd(8)} [${t.sources}]${t.divergence != null && t.divergence > 2 ? " ⚠ divergence " + t.divergence + "%" : ""}`,
  );
console.log(`  DB: ${stats.snapshots} snapshots over ${stats.days} day(s) → Market Watch.md updated`);
