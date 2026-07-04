/** Display formatting helpers — one canonical way to render each data kind. */

/** Token price: 2dp for majors, 4 significant digits for sub-$1 tokens. */
export function formatPrice(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value >= 1) return `$${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  return `$${value.toPrecision(4)}`;
}

/** Compact USD amounts: $47.1B / $25.7M / $263k. */
export function formatMoney(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${Math.round(value / 1e3)}k`;
  return `$${Math.round(value)}`;
}

/** Signed percentage with 2dp: +2.37% / −5.10%. */
export function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

/** Plain thousands-separated integer. */
export function formatInt(value: number | null | undefined): string {
  if (value == null) return "—";
  return Math.round(value).toLocaleString("en-US");
}

/** Relative time: "12s ago" / "3m ago" / "2h ago". */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms)) return "—";
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}
