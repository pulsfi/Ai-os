#!/usr/bin/env node
/**
 * Daily Learning Cycle — the system trains itself day by day on live data.
 *
 * Each run (takes ~3 seconds):
 *   1. Snapshots live Solana mainnet (price, TPS, epoch, validators)
 *   2. Appends today's snapshot to the day-by-day history (history.json)
 *   3. LEARNS from the accumulated history: day-over-day change, 7-day
 *      average, volatility, TPS trend, anomaly detection
 *   4. Writes what it learned to "10 Memory/Training Log.md"
 *   5. Creates today's daily note if missing
 *   6. Raises a 🔴 alert in Monitoring Agent Reports on big moves (±10%)
 *
 * Usage:  node daily-cycle.mjs
 * The more days it runs, the smarter its stats get.
 */

import {
  readFileSync,
  writeFileSync,
  appendFileSync,
  existsSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const VAULT = join(SCRIPT_DIR, "..", "..");
const HISTORY = join(SCRIPT_DIR, "history.json");
const TRAINING_LOG = join(VAULT, "10 Memory", "Training Log.md");
const MONITOR_REPORTS = join(VAULT, "04 Agents", "Monitoring Agent", "Reports.md");
import { CONFIG } from "../lib/env.mjs";
const RPC_URL = CONFIG.rpcUrl;
const ALERT_THRESHOLD = CONFIG.alertThreshold; // percent move that triggers an alert

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

async function safe(fn) {
  try {
    return await fn();
  } catch {
    return null;
  }
}

// ---------- 1. Snapshot live chain ----------
async function snapshot() {
  const [slot, epoch, perf, votes, price] = await Promise.all([
    safe(() => rpc("getSlot")),
    safe(() => rpc("getEpochInfo")),
    safe(() => rpc("getRecentPerformanceSamples", [5])),
    safe(() => rpc("getVoteAccounts")),
    safe(async () => {
      const r = await fetch(
        "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true&include_market_cap=true",
      );
      return (await r.json()).solana;
    }),
  ]);

  let tps = null;
  if (perf?.length) {
    const tx = perf.reduce((s, p) => s + p.numTransactions, 0);
    const secs = perf.reduce((s, p) => s + p.samplePeriodSecs, 0);
    if (secs > 0) tps = Math.round(tx / secs);
  }

  return {
    date: new Date().toISOString().slice(0, 10),
    time: new Date().toISOString().slice(11, 19) + " UTC",
    price: price?.usd ?? null,
    change24h: price?.usd_24h_change != null ? +price.usd_24h_change.toFixed(2) : null,
    marketCapB: price?.usd_market_cap != null ? +(price.usd_market_cap / 1e9).toFixed(1) : null,
    slot,
    epoch: epoch?.epoch ?? null,
    tps,
    validators: votes ? votes.current.length : null,
    delinquent: votes ? votes.delinquent.length : null,
  };
}

// ---------- 3. Learn from accumulated history ----------
function learn(history) {
  const days = history.length;
  const latest = history[days - 1];
  const prev = days > 1 ? history[days - 2] : null;
  const last7 = history.slice(-7);

  const lessons = [];
  const avg = (arr) => arr.reduce((s, v) => s + v, 0) / arr.length;

  // Day-over-day price learning
  let dayChange = null;
  if (prev?.price != null && latest.price != null) {
    dayChange = +(((latest.price - prev.price) / prev.price) * 100).toFixed(2);
    lessons.push(
      `Day-over-day SOL moved **${dayChange >= 0 ? "+" : ""}${dayChange}%** (${prev.price} → ${latest.price} USD).`,
    );
  } else {
    lessons.push("First training day — this snapshot is the baseline. Comparisons unlock tomorrow.");
  }

  // 7-day statistics (get richer as days accumulate)
  const prices = last7.map((d) => d.price).filter((p) => p != null);
  let avg7 = null, vol = null, lo = null, hi = null;
  if (prices.length >= 2) {
    avg7 = +avg(prices).toFixed(2);
    lo = Math.min(...prices);
    hi = Math.max(...prices);
    vol = +(((hi - lo) / avg7) * 100).toFixed(2);
    lessons.push(
      `${prices.length}-day window: avg **$${avg7}**, range $${lo}–$${hi}, volatility **${vol}%**.`,
    );
    if (latest.price > avg7) {
      lessons.push(`Price is **above** its ${prices.length}-day average → short-term uptrend.`);
    } else {
      lessons.push(`Price is **below** its ${prices.length}-day average → short-term downtrend.`);
    }
  }

  // TPS / network learning
  const tpsVals = last7.map((d) => d.tps).filter((t) => t != null);
  if (tpsVals.length >= 2) {
    const tpsAvg = Math.round(avg(tpsVals));
    const drop = latest.tps != null && latest.tps < tpsAvg * 0.5;
    lessons.push(
      `Normal TPS baseline learned: **~${tpsAvg}**.` +
        (drop ? " ⚠️ Today is far below baseline — possible congestion." : ""),
    );
  }

  // Validator health learning
  if (latest.validators != null && latest.delinquent != null) {
    const delinquentPct = +((latest.delinquent / (latest.validators + latest.delinquent)) * 100).toFixed(1);
    if (delinquentPct > 5) lessons.push(`⚠️ Delinquent validators at ${delinquentPct}% — network stress signal.`);
  }

  // Anomaly detection on 24h move
  const alert =
    latest.change24h != null && Math.abs(latest.change24h) >= ALERT_THRESHOLD
      ? `SOL moved ${latest.change24h}% in 24h — exceeds ±${ALERT_THRESHOLD}% threshold`
      : null;

  return { days, latest, prev, dayChange, avg7, vol, lessons, alert };
}

// ---------- 4. Write the Training Log ----------
function writeTrainingLog(history, brain) {
  const rows = history
    .slice(-14)
    .reverse()
    .map(
      (d) =>
        `| ${d.date} | $${d.price ?? "—"} | ${d.change24h != null ? (d.change24h >= 0 ? "+" : "") + d.change24h + "%" : "—"} | ${d.tps ?? "—"} | ${d.epoch ?? "—"} | ${d.validators ?? "—"} |`,
    )
    .join("\n");

  const maturity =
    brain.days >= 7
      ? "🟢 Trained — full weekly statistics available"
      : `🟡 Training — day ${brain.days} of 7 until full weekly statistics`;

  const note = `---
tags: [memory, training, live]
updated: ${brain.latest.date} ${brain.latest.time}
training-days: ${brain.days}
---

# 🧠 Training Log

The system trains itself on **live [[Solana]] mainnet data, one snapshot per day**. Every run adds a day of history and re-derives what it knows. Run by the [[Learning Agent]] + [[Monitoring Agent]] via the [[Automation Hub]].

**Status:** ${maturity}
**Training days:** ${brain.days} · **Last snapshot:** ${brain.latest.date} ${brain.latest.time}

## 📖 What the system learned today

${brain.lessons.map((l) => `- ${l}`).join("\n")}

## 📊 Day-by-Day History (last 14 days)

| Date | SOL Price | 24h | TPS | Epoch | Validators |
|---|---|---|---|---|---|
${rows}

## 🎓 How it gets smarter

| Days of data | Unlocks |
|---|---|
| 1 | Baseline snapshot ${brain.days >= 1 ? "✅" : ""} |
| 2 | Day-over-day comparison ${brain.days >= 2 ? "✅" : ""} |
| 3+ | Trend direction vs. rolling average ${brain.days >= 3 ? "✅" : ""} |
| 7 | Weekly volatility + TPS baseline ${brain.days >= 7 ? "✅" : ""} |
| 30 | Monthly ranges for the [[Strategy Agent]] ${brain.days >= 30 ? "✅" : ""} |

## Related

- [[Solana Live]] — the real-time feed (intra-day)
- [[Memory Hub]] — where durable lessons graduate
- [[Learning Agent]] · [[Monitoring Agent]] · [[Strategy Agent]]
`;
  writeFileSync(TRAINING_LOG, note, "utf8");
}

// ---------- 5. Today's daily note ----------
function ensureDailyNote(brain) {
  const d = brain.latest;
  const path = join(VAULT, "12 Daily Notes", `${d.date}.md`);
  if (existsSync(path)) return false;
  writeFileSync(
    path,
    `---
tags: [daily]
created: ${d.date}
---

# ${d.date}

← Back to [[Home]] · Template: [[Daily Template]] · Auto-created by the daily cycle

## 📡 Live Data (auto)

SOL **$${d.price ?? "—"}** (${d.change24h != null ? (d.change24h >= 0 ? "+" : "") + d.change24h + "%" : "—"} 24h) · TPS ${d.tps ?? "—"} · Epoch ${d.epoch ?? "—"} — details in [[Solana Live]] and the [[Training Log]]

## Goals

## Work Done

## Problems

## Lessons Learned

## Tomorrow
`,
    "utf8",
  );
  return true;
}

// ---------- 6. Alert on anomalies ----------
function raiseAlert(brain) {
  if (!brain.alert) return false;
  const line = `| ${brain.latest.date} | 🔴 | ${brain.alert} — flagged by the [[Training Log]] | [[Risk Agent]] |`;
  const txt = readFileSync(MONITOR_REPORTS, "utf8");
  if (txt.includes(line)) return false; // don't duplicate the same day's alert
  const updated = txt.replace(/(## Alert Log\n\n(?:\|.*\n)+)/, `$1${line}\n`);
  writeFileSync(MONITOR_REPORTS, updated === txt ? txt + "\n" + line + "\n" : updated, "utf8");
  return true;
}

// ---------- main ----------
console.log("🧠 Daily learning cycle starting...");
const t0 = Date.now();

const history = existsSync(HISTORY) ? JSON.parse(readFileSync(HISTORY, "utf8")) : [];
const snap = await snapshot();
if (snap.price == null && snap.slot == null) {
  console.error("✗ No data sources reachable — aborting without writing.");
  process.exit(1);
}

// upsert: re-running on the same day refreshes today's entry instead of duplicating
const i = history.findIndex((d) => d.date === snap.date);
if (i >= 0) history[i] = snap;
else history.push(snap);
writeFileSync(HISTORY, JSON.stringify(history, null, 2), "utf8");

const brain = learn(history);
writeTrainingLog(history, brain);
const createdDaily = ensureDailyNote(brain);
const alerted = raiseAlert(brain);

const secs = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`✓ Training day ${brain.days} recorded (${snap.date}) in ${secs}s`);
console.log(`  SOL $${snap.price} · TPS ${snap.tps} · epoch ${snap.epoch}`);
brain.lessons.forEach((l) => console.log(`  📖 ${l.replace(/\*\*/g, "")}`));
if (createdDaily) console.log(`  📅 Daily note ${snap.date}.md created`);
if (alerted) console.log(`  🔴 Alert raised to Monitoring Agent Reports`);
console.log(`  → 10 Memory/Training Log.md updated`);
