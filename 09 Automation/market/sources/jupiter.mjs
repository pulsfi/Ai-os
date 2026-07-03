// Jupiter — price cross-check + swap routing (free lite tier, no key)
export async function jupPrices(mints) {
  const res = await fetch(
    `https://lite-api.jup.ag/price/v3?ids=${mints.join(",")}`,
  );
  if (!res.ok) throw new Error(`Jupiter HTTP ${res.status}`);
  const json = await res.json();
  const out = {};
  for (const [mint, d] of Object.entries(json)) {
    if (d?.usdPrice != null) out[mint] = Number(d.usdPrice);
  }
  return out; // { mint: priceUsd }
}

// Swap route quote — used by paper trading to sanity-check executability.
export async function jupQuote(inputMint, outputMint, amountLamports) {
  const res = await fetch(
    `https://lite-api.jup.ag/swap/v1/quote?inputMint=${inputMint}&outputMint=${outputMint}&amount=${amountLamports}&slippageBps=50`,
  );
  if (!res.ok) throw new Error(`Jupiter quote HTTP ${res.status}`);
  return await res.json();
}
