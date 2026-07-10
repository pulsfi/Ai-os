"use client";

/**
 * Center panel — price history for the selected token (Recharts), plus
 * live market stats. History comes from the backend's stored snapshots
 * (needs PostgreSQL + the market scheduler); when empty we say so
 * honestly rather than drawing a fake line.
 */
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Skeleton } from "@/components/ui/skeleton";
import { useMarketHistory, useMarketToken } from "@/hooks/use-backend";
import { ApiError } from "@/lib/api/client";
import { formatMoney, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</p>
      <p
        className={cn(
          "font-mono text-sm tabular-nums",
          tone === "up" && "text-emerald-400",
          tone === "down" && "text-red-400",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function TokenChart({ mint, symbol }: { mint: string; symbol?: string }) {
  const token = useMarketToken(mint);
  const history = useMarketHistory(mint, 100);

  const points = (history.data ?? [])
    .filter((h) => h.price_usd !== null)
    .map((h) => ({ t: new Date(h.ts).getTime(), price: h.price_usd as number }))
    .sort((a, b) => a.t - b.t);
  const up = (token.data?.market.change_24h ?? 0) >= 0;

  return (
    <div className="flex h-full flex-col rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-base font-semibold">{symbol || `${mint.slice(0, 6)}…`}</span>
          <span className="font-mono text-lg">{formatPrice(token.data?.market.price_usd)}</span>
          <span className={cn("font-mono text-sm", up ? "text-emerald-400" : "text-red-400")}>
            {formatPct(token.data?.market.change_24h)}
          </span>
        </div>
        <div className="flex gap-5">
          <Stat label="24h Vol" value={formatMoney(token.data?.market.volume_24h)} />
          <Stat label="Liquidity" value={formatMoney(token.data?.market.liquidity_usd)} />
          <Stat label="Mcap" value={formatMoney(token.data?.market.market_cap)} />
        </div>
      </div>

      <div className="flex-1 p-2">
        {history.isLoading && <Skeleton className="h-full min-h-56 rounded-lg" />}
        {history.isError && !history.isLoading && (
          <div className="flex h-full min-h-56 items-center justify-center p-4 text-center text-xs text-muted-foreground">
            {history.error instanceof ApiError
              ? history.error.message
              : "History unavailable."}{" "}
            Price snapshots need PostgreSQL + the market scheduler running.
          </div>
        )}
        {history.data && points.length < 2 && !history.isLoading && (
          <div className="flex h-full min-h-56 items-center justify-center text-center text-xs text-muted-foreground">
            Not enough stored history yet — the curve fills in as snapshots accumulate.
          </div>
        )}
        {points.length >= 2 && (
          <ResponsiveContainer width="100%" height="100%" minHeight={224}>
            <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="px" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={up ? "#34d399" : "#f87171"} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={up ? "#34d399" : "#f87171"} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="t" type="number" domain={["dataMin", "dataMax"]} scale="time"
                tickFormatter={(t) => new Date(t).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
                tick={{ fontSize: 10 }} stroke="currentColor" className="text-muted-foreground"
                tickLine={false} axisLine={false} minTickGap={40}
              />
              <YAxis
                domain={["auto", "auto"]} width={56} tick={{ fontSize: 10 }}
                stroke="currentColor" className="text-muted-foreground"
                tickFormatter={(v) => formatPrice(v)} tickLine={false} axisLine={false}
              />
              <Tooltip
                contentStyle={{ background: "rgba(15,17,23,0.95)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, fontSize: 12, color: "#e5e7eb" }}
                labelStyle={{ color: "#9ca3af" }}
                labelFormatter={(t) => new Date(t as number).toLocaleString()}
                formatter={(v) => [formatPrice(Number(v)), "price"]}
              />
              <Area type="monotone" dataKey="price" stroke={up ? "#34d399" : "#f87171"} strokeWidth={2} fill="url(#px)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
