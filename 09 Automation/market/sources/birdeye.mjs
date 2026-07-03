// Birdeye — token prices (requires free API key; optional)
// Get a key at birdeye.so → add "birdeyeApiKey" to scripts/config.json.
export async function bePrice(mint, apiKey) {
  if (!apiKey) return null; // not configured — skip quietly
  const res = await fetch(
    `https://public-api.birdeye.so/defi/price?address=${mint}`,
    { headers: { "X-API-KEY": apiKey, "x-chain": "solana" } },
  );
  if (!res.ok) throw new Error(`Birdeye HTTP ${res.status}`);
  const json = await res.json();
  return json.data?.value ?? null;
}
