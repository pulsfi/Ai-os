// DexScreener — DEX market data per token mint (free, no key)
// Returns the deepest-liquidity Solana pair for the mint.
export async function dsToken(mint) {
  const res = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${mint}`);
  if (!res.ok) throw new Error(`DexScreener HTTP ${res.status}`);
  const json = await res.json();
  // only pairs where this mint is the BASE token — priceUsd refers to the base.
  // Trust only major quote tokens: exotic pairs (e.g. JUP/JTO) report bad priceUsd.
  const MAJORS = new Set(["SOL", "USDC", "USDT", "WSOL"]);
  let pairs = (json.pairs || []).filter(
    (p) => p.chainId === "solana" && p.baseToken?.address === mint,
  );
  const majorPairs = pairs.filter((p) => MAJORS.has(p.quoteToken?.symbol));
  if (majorPairs.length) pairs = majorPairs;
  if (!pairs.length) return null;
  const best = pairs.reduce((a, b) =>
    (b.liquidity?.usd || 0) > (a.liquidity?.usd || 0) ? b : a,
  );
  return {
    priceUsd: best.priceUsd != null ? Number(best.priceUsd) : null,
    liquidityUsd: best.liquidity?.usd ?? null,
    volume24h: best.volume?.h24 ?? null,
    change24h: best.priceChange?.h24 ?? null,
    fdv: best.fdv ?? null,
    dex: best.dexId,
    pair: best.pairAddress,
  };
}
