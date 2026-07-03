#!/usr/bin/env node
/**
 * Meme Scalper — autonomous quick-trade agent (PAPER MODE).
 *
 * Every cycle it behaves like a disciplined meme coin scalper:
 *   1. SCAN    — GeckoTerminal trending Solana pools (the meme radar)
 *   2. FILTER  — momentum entries only: m5 & h1 up, real volume, buyers > sellers
 *   3. RISK    — Stage 4 Risk Engine on every candidate (mint/freeze/liquidity/age);
 *                ⛔ block = never traded, ⚠️ caution = half size
 *   4. ENTER   — paper position at live price, reasoning recorded
 *   5. MANAGE  — take-profit / stop-loss / max-hold exits, checked every cycle
 *
 * All trades go to the shared paper_trades DB → [[Paper Trading]] scoreboard.
 * LIVE EXECUTION IS NOT WIRED. That is Stage 5, gated on this bot's track record.
 *
 * Usage:
 *   node scalper.mjs              # one cycle
 *   node scalper.mjs --loop       # run forever (interval from .env, default 60s)
 *   node scalper.mjs --cycles 3   # run N cycles then stop
 */
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { CONFIG } from "../lib/env.mjs";
import { trendingPools } from "./sources/geckoterminal.mjs";
import { dsToken } from "./sources/dexscreener.mjs";
import { scoreToken } from "./risk-engine.mjs";
import { openDb } from "./db.mjs";

const DIR = dirname(fileURLToPath(import.meta.url));
const VAULT = join(DIR, "..", "..");
const NOTE = join(VAULT, "07 Strategies", "Scalper Live.md");

// --- strategy settings (override in 09 Automation/.env) ---
const env = (k, d) => Number(process.env[k] ?? d);
const S = {
  positionUsd: env("SCALP_POSITION_USD", 25), // full size per scalp (paper $)
  maxOpen: env("SCALP_MAX_OPEN", 3),          // max simultaneous positions
  tpPct: env("SCALP_TP", 8),                  // take profit %
  slPct: env("SCALP_SL", 5),                  // stop loss %
  maxHoldMin: env("SCALP_MAX_HOLD_MIN", 45),  // time stop
  minLiq: env("SCALP_MIN_LIQ", 50_000),       // min pool liquidity $
  minAgeH: env("SCALP_MIN_AGE_H", 1),         // skip pools younger than this
  minVolH1: env("SCALP_MIN_VOL_H1", 10_000),  // min 1h volume $
  cooldownMin: env("SCALP_COOLDOWN_MIN", 60), // no re-entry after closing
  intervalS: env("SCALP_INTERVAL", 60),       // loop interval seconds
};

const db = openDb();
const TAG = "[SCALPER]";
const now = () => new Date().toISOString().replace("T", " ").slice(0, 19) + " UTC";
const px = (n) => (n == null ? "—" : n >= 1 ? `$${n.toFixed(2)}` : `$${n.toPrecision(4)}`);

const openScalps = () =>
  db.prepare(`SELECT * FROM paper_trades WHERE status='open' AND reasoning LIKE '${TAG}%'`).all();

function recentlyTraded(mint) {
  const r = db
    .prepare(
      `SELECT MAX(COALESCE(exit_ts, entry_ts)) t FROM paper_trades WHERE mint=? AND reasoning LIKE '${TAG}%'`,
    )
    .get(mint);
  if (!r?.t) return false;
  return Date.now() - new Date(r.t.replace(" UTC", "Z").replace(" ", "T")).getTime() <
    S.cooldownMin * 60_000;
}

async function livePrice(mint) {
  const d = await dsToken(mint).catch(() => null);
  return d?.priceUsd ?? null;
}

// ---------- manage open positions ----------
async function manage(log) {
  for (const t of openScalps()) {
    const price = await livePrice(t.mint);
    if (price == null) continue;
    const pnlPct = ((price - t.entry_price) / t.entry_price) * 100;
    const heldMin = (Date.now() - new Date(t.entry_ts.replace(" UTC", "Z").replace(" ", "T")).getTime()) / 60_000;
    let exit = null;
    if (pnlPct >= S.tpPct) exit = `take-profit +${S.tpPct}% hit`;
    else if (pnlPct <= -S.slPct) exit = `stop-loss -${S.slPct}% hit`;
    else if (heldMin >= S.maxHoldMin) exit = `time stop ${S.maxHoldMin}min`;
    if (exit) {
      const pnlUsd = (t.usd_size * pnlPct) / 100;
      db.prepare(
        `UPDATE paper_trades SET exit_price=?, exit_ts=?, pnl_usd=?, pnl_pct=?, exit_note=?, status='closed' WHERE id=?`,
      ).run(price, now(), +pnlUsd.toFixed(2), +pnlPct.toFixed(2), exit, t.id);
      log.push(`📕 CLOSE #${t.id} ${t.symbol}: ${px(t.entry_price)} → ${px(price)} = ${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}% (${exit})`);
    } else {
      log.push(`⏳ HOLD #${t.id} ${t.symbol}: ${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}% after ${Math.round(heldMin)}min`);
    }
  }
}

// ---------- scan & enter ----------
async function scanAndEnter(log) {
  const pools = await trendingPools().catch((e) => (log.push(`! radar down: ${e.message}`), []));
  const candidates = pools.filter(
    (p) =>
      p.liquidityUsd >= S.minLiq &&
      p.ageHours >= S.minAgeH &&
      p.vol.h1 >= S.minVolH1 &&
      p.change.m5 > 1 &&
      p.change.h1 > 0 &&
      (p.buys5 ?? 0) > (p.sells5 ?? 0),
  );
  log.push(`📡 scanned ${pools.length} trending pools → ${candidates.length} momentum candidate(s)`);

  for (const c of candidates) {
    if (openScalps().length >= S.maxOpen) { log.push(`🧊 max ${S.maxOpen} positions open — no new entries`); break; }
    if (openScalps().some((t) => t.mint === c.mint)) continue;
    if (recentlyTraded(c.mint)) { log.push(`🕐 ${c.symbol}: cooldown — skipped`); continue; }

    const risk = await scoreToken(c.mint, { liquidityUsd: c.liquidityUsd, ageHours: c.ageHours });
    if (risk.verdict === "block") {
      log.push(`⛔ ${c.symbol}: BLOCKED by risk engine (${risk.score}/10) — ${risk.flags.filter((f) => f.startsWith("🔴")).join("; ") || "critical"}`);
      continue;
    }
    const size = risk.verdict === "caution" ? S.positionUsd / 2 : S.positionUsd;
    const price = (await livePrice(c.mint)) ?? c.priceUsd;
    if (price == null) continue;

    const reasoning = `${TAG} momentum: m5 +${c.change.m5}%, h1 +${c.change.h1}%, vol1h $${Math.round(c.vol.h1 / 1000)}k, buys/sells ${c.buys5}/${c.sells5}; risk ${risk.score}/10 ${risk.verdict}${risk.verdict === "caution" ? " (half size)" : ""}`;
    const r = db
      .prepare(`INSERT INTO paper_trades (symbol, mint, usd_size, entry_price, entry_ts, reasoning) VALUES (?, ?, ?, ?, ?, ?)`)
      .run(c.symbol, c.mint, size, price, now(), reasoning);
    log.push(`🟢 OPEN #${r.lastInsertRowid} ${c.symbol} $${size} @ ${px(price)} — ${reasoning.slice(TAG.length + 1)}`);
  }
}

// ---------- vault note ----------
function writeNote(cycleLog) {
  const open = openScalps();
  const closed = db
    .prepare(`SELECT * FROM paper_trades WHERE status='closed' AND reasoning LIKE '${TAG}%' ORDER BY exit_ts DESC LIMIT 20`)
    .all();
  const stats = db
    .prepare(`SELECT COUNT(*) n, SUM(pnl_usd>0) w, ROUND(SUM(pnl_usd),2) pnl FROM paper_trades WHERE status='closed' AND reasoning LIKE '${TAG}%'`)
    .get();

  const openRows = open.length
    ? open.map((t) => `| #${t.id} | **${t.symbol}** | $${t.usd_size} | ${px(t.entry_price)} | ${t.entry_ts} |`).join("\n")
    : "| — | *flat — waiting for a setup* | | | |";
  const closedRows = closed.length
    ? closed.map((t) => `| #${t.id} | **${t.symbol}** | ${px(t.entry_price)} → ${px(t.exit_price)} | ${t.pnl_usd >= 0 ? "🟢 +" : "🔴 "}$${Math.abs(t.pnl_usd).toFixed(2)} (${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct}%) | ${t.exit_note} |`).join("\n")
    : "| — | *none yet* | | | |";

  writeFileSync(
    NOTE,
    `---
tags: [strategy, scalper, live, paper-trading]
updated: ${now()}
---

# ⚡ Scalper Live (Paper Mode)

Autonomous meme coin scalper — scans trending [[Solana]] pools, risk-checks every token through the **Stage 4 Risk Engine**, and takes quick momentum scalps **on paper at real live prices**. Strategy of the [[Strategy Agent]], safety by the [[Risk Agent]], results reviewed by the [[Learning Agent]].

← [[Home]] · Full trade DB: [[Paper Trading]] · Radar: GeckoTerminal trending

## ⚙️ Strategy Settings (edit in \`09 Automation/.env\`)

| Size/trade | Max open | Take profit | Stop loss | Time stop | Min liquidity | Min pool age | Cooldown |
|---|---|---|---|---|---|---|---|
| $${S.positionUsd} | ${S.maxOpen} | +${S.tpPct}% | −${S.slPct}% | ${S.maxHoldMin} min | $${S.minLiq.toLocaleString()} | ${S.minAgeH}h | ${S.cooldownMin} min |

## 📈 Scalp Scoreboard

| Closed scalps | Wins | Total P&L (paper) |
|---|---|---|
| ${stats.n ?? 0} | ${stats.w ?? 0} | ${(stats.pnl ?? 0) >= 0 ? "🟢 +" : "🔴 "}$${Math.abs(stats.pnl ?? 0).toFixed(2)} |

## 🔓 Open Scalps

| ID | Token | Size | Entry | Opened |
|---|---|---|---|---|
${openRows}

## 📕 Recent Closed Scalps

| ID | Token | Entry → Exit | P&L | Exit reason |
|---|---|---|---|---|
${closedRows}

## 🖥️ Last Cycle — ${now()}

\`\`\`
${cycleLog.join("\n") || "(quiet cycle)"}
\`\`\`

## ⛔ The Stage 5 gate

This bot trades **paper money at real prices**. Live execution stays locked until the scoreboard proves consistent profit over a real track record — reviewed by the [[Learning Agent]], enforced by the [[Risk Agent]], per the [[AI Solana System]] roadmap.

## Related

- [[Paper Trading]] · [[Market Watch]] · [[Market Data Service]] · [[Agent Control Center]]
`,
    "utf8",
  );
}

// ---------- cycle ----------
async function cycle(n) {
  const log = [];
  const t0 = Date.now();
  await manage(log);       // exits first — protect positions before chasing new ones
  await scanAndEnter(log);
  writeNote(log);
  try {
    execFileSync(process.execPath, [join(DIR, "paper-trade.mjs"), "status"], { stdio: "ignore" });
  } catch {}
  console.log(`── cycle ${n} (${((Date.now() - t0) / 1000).toFixed(1)}s) ──`);
  log.forEach((l) => console.log("  " + l));
}

// ---------- main ----------
const argv = process.argv.slice(2);
const loop = argv.includes("--loop");
const ci = argv.indexOf("--cycles");
const cycles = ci !== -1 ? Number(argv[ci + 1]) || 1 : loop ? Infinity : 1;

console.log(`⚡ Meme Scalper — PAPER MODE · $${S.positionUsd}/scalp · TP +${S.tpPct}% / SL −${S.slPct}% / ${S.maxHoldMin}min · interval ${S.intervalS}s`);
let n = 1;
await cycle(n);
while (n < cycles) {
  await new Promise((r) => setTimeout(r, S.intervalS * 1000));
  n++;
  await cycle(n).catch((e) => console.error("cycle error:", e.message));
}
