#!/usr/bin/env node
/**
 * Paper Trading — Stage 3, Step 5. Hypothetical trades at REAL live prices.
 * No wallet, no keys, no real funds — records entry/exit/P&L/reasoning so the
 * system's judgment can be tested before any live execution (Stage 5).
 *
 * Usage:
 *   node paper-trade.mjs open <SYMBOL> <usd> "<reasoning>"   # enter at live price
 *   node paper-trade.mjs close <id> ["<exit note>"]          # exit at live price
 *   node paper-trade.mjs status                              # portfolio + P&L
 *
 * Every command refreshes "07 Strategies/Paper Trading.md".
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { dsToken } from "./sources/dexscreener.mjs";
import { cgPrices } from "./sources/coingecko.mjs";
import { openDb, dbStats } from "./db.mjs";

const DIR = dirname(fileURLToPath(import.meta.url));
const VAULT = join(DIR, "..", "..");
const NOTE = join(VAULT, "07 Strategies", "Paper Trading.md");
const watchlist = JSON.parse(readFileSync(join(DIR, "watchlist.json"), "utf8"));
const db = openDb();

async function livePrice(token) {
  const d = await dsToken(token.mint).catch(() => null);
  if (d?.priceUsd != null) return { price: d.priceUsd, source: "dexscreener" };
  const g = await cgPrices([token.coingeckoId]).catch(() => null);
  const p = g?.[token.coingeckoId]?.usd;
  if (p != null) return { price: p, source: "coingecko" };
  throw new Error(`no live price for ${token.symbol}`);
}

const px = (n) => (n == null ? "—" : n >= 1 ? `$${n.toFixed(2)}` : `$${n.toPrecision(4)}`);
const now = () => new Date().toISOString().replace("T", " ").slice(0, 19) + " UTC";

function writeNote() {
  const open = db.prepare("SELECT * FROM paper_trades WHERE status='open' ORDER BY id").all();
  const closed = db.prepare("SELECT * FROM paper_trades WHERE status='closed' ORDER BY exit_ts DESC").all();
  const s = dbStats(db);
  const wins = closed.filter((t) => t.pnl_usd > 0).length;
  const winRate = closed.length ? Math.round((wins / closed.length) * 100) : null;

  const openRows = open.length
    ? open
        .map(
          (t) =>
            `| #${t.id} | **${t.symbol}** | $${t.usd_size} | ${px(t.entry_price)} | ${t.entry_ts} | ${t.reasoning ?? ""} |`,
        )
        .join("\n")
    : "| — | *no open positions* | | | | |";

  const closedRows = closed.length
    ? closed
        .map(
          (t) =>
            `| #${t.id} | **${t.symbol}** | $${t.usd_size} | ${px(t.entry_price)} | ${px(t.exit_price)} | ${t.pnl_usd >= 0 ? "🟢 +" : "🔴 "}$${Math.abs(t.pnl_usd).toFixed(2)} (${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct.toFixed(2)}%) | ${t.reasoning ?? ""}${t.exit_note ? " → " + t.exit_note : ""} |`,
        )
        .join("\n")
    : "| — | *none yet* | | | | | |";

  writeFileSync(
    NOTE,
    `---
tags: [strategy, paper-trading, live]
updated: ${now()}
---

# 🧪 Paper Trading

Hypothetical trades executed at **real live prices** — Stage 3 of the [[AI Solana System]] roadmap. This is where the [[Strategy Agent]]'s ideas are tested and the [[Learning Agent]] compares predictions with outcomes. **No real funds are ever used here.**

← [[Home]] · Prices: [[Market Watch]] · Rules: [[Trading#Risk Management|Trading risk rules]]

## 📈 Scoreboard

| Closed trades | Win rate | Total P&L (paper) |
|---|---|---|
| ${closed.length} | ${winRate == null ? "—" : winRate + "%"} | ${s.totalPnl >= 0 ? "🟢 +" : "🔴 "}$${Math.abs(s.totalPnl).toFixed(2)} |

## 🔓 Open Positions

| ID | Token | Size | Entry | Opened | Reasoning |
|---|---|---|---|---|---|
${openRows}

## 📕 Closed Trades

| ID | Token | Size | Entry | Exit | P&L | Reasoning |
|---|---|---|---|---|---|---|
${closedRows}

## How to trade (paper)

\`\`\`
node "09 Automation/market/paper-trade.mjs" open SOL 100 "reason for entry"
node "09 Automation/market/paper-trade.mjs" close 1 "reason for exit"
node "09 Automation/market/paper-trade.mjs" status
\`\`\`

## The gate to real execution

Per the roadmap, the [[Execution Agent]] stays on standby until this log shows **consistent performance** — reviewed by the [[Learning Agent]] and [[Risk Agent]]. Only then does Stage 5 (small live execution) begin.

## Related

- [[Market Watch]] · [[Strategy Hub]] · [[Training Log]] · [[Agent Control Center]]
`,
    "utf8",
  );
}

const [, , cmd, ...args] = process.argv;

if (cmd === "open") {
  const [symRaw, usdRaw, ...reasonParts] = args;
  const token = watchlist.find((w) => w.symbol.toUpperCase() === (symRaw || "").toUpperCase());
  if (!token) throw new Error(`unknown symbol "${symRaw}" — add it to watchlist.json first`);
  const usd = Number(usdRaw);
  if (!(usd > 0)) throw new Error("size must be a positive USD amount");
  const reasoning = reasonParts.join(" ") || null;
  const { price, source } = await livePrice(token);
  const r = db
    .prepare(
      `INSERT INTO paper_trades (symbol, mint, usd_size, entry_price, entry_ts, reasoning) VALUES (?, ?, ?, ?, ?, ?)`,
    )
    .run(token.symbol, token.mint, usd, price, now(), reasoning);
  writeNote();
  console.log(`✓ PAPER OPEN #${r.lastInsertRowid}: ${token.symbol} $${usd} @ ${px(price)} (live via ${source})`);
  if (reasoning) console.log(`  reasoning: ${reasoning}`);
} else if (cmd === "close") {
  const id = Number(args[0]);
  const exitNote = args.slice(1).join(" ") || null;
  const t = db.prepare("SELECT * FROM paper_trades WHERE id=? AND status='open'").get(id);
  if (!t) throw new Error(`no open paper trade #${id}`);
  const token = watchlist.find((w) => w.symbol === t.symbol) ?? { mint: t.mint, coingeckoId: "" };
  const { price, source } = await livePrice(token);
  const pnlPct = ((price - t.entry_price) / t.entry_price) * 100;
  const pnlUsd = (t.usd_size * pnlPct) / 100;
  db.prepare(
    `UPDATE paper_trades SET exit_price=?, exit_ts=?, pnl_usd=?, pnl_pct=?, exit_note=?, status='closed' WHERE id=?`,
  ).run(price, now(), +pnlUsd.toFixed(2), +pnlPct.toFixed(2), exitNote, id);
  writeNote();
  console.log(
    `✓ PAPER CLOSE #${id}: ${t.symbol} ${px(t.entry_price)} → ${px(price)} (live via ${source})  P&L ${pnlUsd >= 0 ? "+" : ""}$${pnlUsd.toFixed(2)} (${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%)`,
  );
} else if (cmd === "status" || !cmd) {
  const s = dbStats(db);
  writeNote();
  console.log(`Paper trading: ${s.trades ?? 0} trades (${s.openTrades} open), total P&L $${s.totalPnl}`);
  console.log("→ 07 Strategies/Paper Trading.md refreshed");
} else {
  console.log('Usage: open <SYMBOL> <usd> "<reasoning>" | close <id> ["<note>"] | status');
}
