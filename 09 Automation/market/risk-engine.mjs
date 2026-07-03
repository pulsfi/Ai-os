#!/usr/bin/env node
/**
 * Risk Engine — Stage 4. Automated token safety scoring (the Risk Agent's
 * checklist from the vault, executed on-chain):
 *
 *   1. Mint authority revoked?    (live mint = supply can be inflated → BLOCK)
 *   2. Freeze authority revoked?  (live freeze = your tokens can be locked → BLOCK)
 *   3. Liquidity depth            (thin pools = can't exit)
 *   4. Holder concentration       (top-10 accounts vs supply, approx — LPs included)
 *   5. Pool age                   (brand-new pools are rug-prone)
 *
 * Score 0-10 (lower = safer). Verdict: ✅ pass (0-2) / ⚠️ caution (3-5) / ⛔ block (6+ or any critical).
 *
 * CLI:   node risk-engine.mjs <mint> [liquidityUsd] [ageHours]
 * API:   import { scoreToken } from "./risk-engine.mjs"
 */
import { CONFIG } from "../lib/env.mjs";

const RPC_URL = CONFIG.rpcUrl;

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

export async function scoreToken(mint, { liquidityUsd = null, ageHours = null } = {}) {
  const flags = [];
  let score = 0;
  let critical = false;

  // --- on-chain: mint & freeze authority ---
  const info = await rpc("getAccountInfo", [mint, { encoding: "jsonParsed" }]).catch(() => null);
  const parsed = info?.value?.data?.parsed?.info;
  if (!parsed) {
    flags.push("🔴 could not read mint account on-chain");
    score += 3;
  } else {
    if (parsed.mintAuthority != null) {
      flags.push("🔴 MINT AUTHORITY LIVE — supply can be inflated");
      score += 4;
      critical = true;
    }
    if (parsed.freezeAuthority != null) {
      flags.push("🔴 FREEZE AUTHORITY LIVE — tokens can be frozen");
      score += 3;
      critical = true;
    }
    if (parsed.mintAuthority == null && parsed.freezeAuthority == null)
      flags.push("🟢 mint & freeze authority revoked");
  }

  // --- holder concentration (approx: includes LP/exchange accounts) ---
  const [largest, supply] = await Promise.all([
    rpc("getTokenLargestAccounts", [mint]).catch(() => null),
    rpc("getTokenSupply", [mint]).catch(() => null),
  ]);
  let top10Pct = null;
  if (largest?.value?.length && supply?.value?.uiAmount > 0) {
    const top10 = largest.value.slice(0, 10).reduce((s, a) => s + (a.uiAmount || 0), 0);
    top10Pct = +((top10 / supply.value.uiAmount) * 100).toFixed(1);
    if (top10Pct > 80) {
      flags.push(`🔴 top-10 accounts hold ${top10Pct}% of supply`);
      score += 3;
    } else if (top10Pct > 60) {
      flags.push(`⚠️ top-10 accounts hold ${top10Pct}% of supply (incl. LPs)`);
      score += 2;
    } else {
      flags.push(`🟢 top-10 concentration ${top10Pct}% (incl. LPs)`);
    }
  }

  // --- liquidity depth ---
  if (liquidityUsd != null) {
    if (liquidityUsd < 10_000) {
      flags.push(`🔴 liquidity $${Math.round(liquidityUsd).toLocaleString()} — exit trap`);
      score += 4;
      critical = true;
    } else if (liquidityUsd < 50_000) {
      flags.push(`⚠️ thin liquidity $${Math.round(liquidityUsd).toLocaleString()}`);
      score += 2;
    } else {
      flags.push(`🟢 liquidity $${Math.round(liquidityUsd).toLocaleString()}`);
    }
  }

  // --- pool age ---
  if (ageHours != null) {
    if (ageHours < 1) {
      flags.push(`⚠️ pool is ${Math.round(ageHours * 60)} min old — rug window`);
      score += 2;
    } else if (ageHours < 24) {
      flags.push(`⚠️ pool is ${ageHours.toFixed(1)}h old`);
      score += 1;
    } else {
      flags.push(`🟢 pool age ${(ageHours / 24).toFixed(1)}d`);
    }
  }

  score = Math.min(10, score);
  const verdict = critical || score >= 6 ? "block" : score >= 3 ? "caution" : "pass";
  return { mint, score, verdict, critical, top10Pct, flags };
}

// --- CLI ---
if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/").split("/").pop())) {
  const [, , mint, liq, age] = process.argv;
  if (!mint) {
    console.log("Usage: node risk-engine.mjs <mint> [liquidityUsd] [ageHours]");
    process.exit(1);
  }
  const r = await scoreToken(mint, {
    liquidityUsd: liq ? Number(liq) : null,
    ageHours: age ? Number(age) : null,
  });
  const icon = r.verdict === "pass" ? "✅" : r.verdict === "caution" ? "⚠️" : "⛔";
  console.log(`${icon} ${r.verdict.toUpperCase()} — risk score ${r.score}/10`);
  r.flags.forEach((f) => console.log("  " + f));
}
