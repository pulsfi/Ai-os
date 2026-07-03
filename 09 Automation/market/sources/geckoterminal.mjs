// GeckoTerminal — trending & new Solana pools (free, no key). The meme radar.
const BASE = "https://api.geckoterminal.com/api/v2";

function parsePool(p) {
  const a = p.attributes || {};
  const baseId = p.relationships?.base_token?.data?.id || "";
  const mint = baseId.startsWith("solana_") ? baseId.slice(7) : null;
  const pc = a.price_change_percentage || {};
  const vol = a.volume_usd || {};
  const tx5 = a.transactions?.m5 || {};
  return {
    name: a.name,
    symbol: (a.name || "").split(" /")[0].trim(),
    mint,
    priceUsd: a.base_token_price_usd != null ? Number(a.base_token_price_usd) : null,
    liquidityUsd: a.reserve_in_usd != null ? Number(a.reserve_in_usd) : null,
    fdv: a.fdv_usd != null ? Number(a.fdv_usd) : null,
    createdAt: a.pool_created_at || null,
    ageHours: a.pool_created_at
      ? (Date.now() - new Date(a.pool_created_at).getTime()) / 3.6e6
      : null,
    change: {
      m5: pc.m5 != null ? Number(pc.m5) : null,
      h1: pc.h1 != null ? Number(pc.h1) : null,
      h24: pc.h24 != null ? Number(pc.h24) : null,
    },
    vol: {
      m5: vol.m5 != null ? Number(vol.m5) : null,
      h1: vol.h1 != null ? Number(vol.h1) : null,
      h24: vol.h24 != null ? Number(vol.h24) : null,
    },
    buys5: tx5.buys ?? null,
    sells5: tx5.sells ?? null,
  };
}

export async function trendingPools() {
  const res = await fetch(`${BASE}/networks/solana/trending_pools?page=1`);
  if (!res.ok) throw new Error(`GeckoTerminal HTTP ${res.status}`);
  const json = await res.json();
  return (json.data || []).map(parsePool).filter((p) => p.mint);
}

export async function newPools() {
  const res = await fetch(`${BASE}/networks/solana/new_pools?page=1`);
  if (!res.ok) throw new Error(`GeckoTerminal HTTP ${res.status}`);
  const json = await res.json();
  return (json.data || []).map(parsePool).filter((p) => p.mint);
}
