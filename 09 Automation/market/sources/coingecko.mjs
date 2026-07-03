// CoinGecko — general crypto prices (free, no key)
export async function cgPrices(ids) {
  const url =
    "https://api.coingecko.com/api/v3/simple/price?vs_currencies=usd" +
    "&include_24hr_change=true&include_market_cap=true&include_24hr_vol=true" +
    `&ids=${ids.join(",")}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`CoinGecko HTTP ${res.status}`);
  return await res.json(); // { id: { usd, usd_24h_change, usd_market_cap, usd_24h_vol } }
}
