// Solana RPC — chain status (Helius/QuickNode ready: swap rpcUrl in config.json)
export async function chainStatus(rpcUrl) {
  const call = async (method, params = []) => {
    const res = await fetch(rpcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
    });
    const json = await res.json();
    if (json.error) throw new Error(json.error.message);
    return json.result;
  };
  const [health, slot, epoch, perf] = await Promise.all([
    call("getHealth").catch(() => null),
    call("getSlot").catch(() => null),
    call("getEpochInfo").catch(() => null),
    call("getRecentPerformanceSamples", [3]).catch(() => null),
  ]);
  let tps = null;
  if (perf?.length) {
    const tx = perf.reduce((s, p) => s + p.numTransactions, 0);
    const secs = perf.reduce((s, p) => s + p.samplePeriodSecs, 0);
    if (secs > 0) tps = Math.round(tx / secs);
  }
  return { health, slot, epoch: epoch?.epoch ?? null, tps };
}
