"use client";

/**
 * Execution log — EVERY trade in one place, terminal style.
 *
 * Merges the whole bot fleet's ledger (sniper/graduate/trend, live via
 * the WebSocket overlay) with the Node scalper's paper ledger into one
 * chronological stream. Dense monospace rows, color-coded outcomes,
 * exit reasons inline. 100% real data — this is the system's actual
 * record, not a highlight reel.
 */
import * as React from "react";
import { ScrollText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useBotTrades, usePaperTrades } from "@/hooks/use-backend";
import { useFleetLive } from "@/hooks/use-fleet-live";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BotTrade, PaperTrade } from "@/lib/api/schemas";

interface Row {
  key: string;
  ts: string; // sort key: exit time when closed, else entry time
  entryTs: string;
  source: string; // bot id or "scalper"
  symbol: string;
  status: "open" | "closed";
  size: number;
  entry: number;
  exit: number | null;
  pnlUsd: number | null;
  pnlPct: number | null;
  note: string;
}

function fromBotTrade(t: BotTrade): Row {
  return {
    key: `bot-${t.id}`,
    ts: t.exit_ts ?? t.entry_ts,
    entryTs: t.entry_ts,
    source: t.bot_id,
    symbol: t.symbol,
    status: t.status === "open" ? "open" : "closed",
    size: t.usd_size,
    entry: t.entry_price,
    exit: t.exit_price,
    pnlUsd: t.pnl_usd,
    pnlPct: t.pnl_pct,
    note: t.status === "open" ? (t.entry_note ?? "") : (t.exit_note ?? ""),
  };
}

function fromScalperTrade(t: PaperTrade): Row {
  return {
    key: `scalper-${t.id}`,
    ts: t.exit_ts ?? t.entry_ts,
    entryTs: t.entry_ts,
    source: "scalper",
    symbol: t.symbol,
    status: t.status === "open" ? "open" : "closed",
    size: t.usd_size,
    entry: t.entry_price,
    exit: t.exit_price,
    pnlUsd: t.pnl_usd,
    pnlPct: t.pnl_pct,
    note: (t.status === "open" ? t.reasoning : (t.exit_note ?? t.reasoning)) ?? "",
  };
}

const SOURCE_TONE: Record<string, string> = {
  sniper: "text-fuchsia-400",
  graduate: "text-cyan-400",
  trend: "text-amber-400",
  scalper: "text-violet-400",
};

function clock(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "--:--:--"
    : d.toLocaleTimeString("en-GB", { hour12: false });
}

export function ExecutionLog() {
  const fleet = useFleetLive();
  const botTrades = useBotTrades(null, 100);
  const scalperTrades = usePaperTrades(100);
  const [filter, setFilter] = React.useState<string | null>(null);

  // WS snapshot carries the newest fleet trades — overlay it on the
  // polled list so closes/opens appear within ~3s.
  const mergedBots = React.useMemo(() => {
    const byId = new Map<string, BotTrade>();
    for (const t of botTrades.data ?? []) byId.set(String(t.id), t);
    for (const t of fleet.trades ?? []) byId.set(String(t.id), t);
    return [...byId.values()];
  }, [botTrades.data, fleet.trades]);

  const rows = React.useMemo(() => {
    const all = [
      ...mergedBots.map(fromBotTrade),
      ...(scalperTrades.data ?? []).map(fromScalperTrade),
    ];
    all.sort((a, b) => (a.ts < b.ts ? 1 : -1));
    return filter ? all.filter((r) => r.source === filter) : all;
  }, [mergedBots, scalperTrades.data, filter]);

  const sources = ["sniper", "graduate", "trend", "scalper"];
  const isLoading = botTrades.isLoading || scalperTrades.isLoading;

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <div className="flex items-center gap-2">
          <ScrollText className="size-4 text-primary" />
          <span className="text-sm font-semibold">Execution log</span>
          <Badge variant="outline" className="font-mono text-[10px]">
            {rows.length} trades
          </Badge>
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => setFilter(null)}
            className={cn(
              "rounded px-2 py-0.5 text-[10px] uppercase tracking-wider transition-colors",
              filter === null
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            all
          </button>
          {sources.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFilter(s)}
              className={cn(
                "rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider transition-colors",
                filter === s
                  ? "bg-primary/15 text-primary"
                  : cn("hover:bg-muted", SOURCE_TONE[s]),
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="space-y-1.5 p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-7 rounded" />
          ))}
        </div>
      )}
      {botTrades.isError && !isLoading && (
        <div className="p-4">
          <WidgetError error={botTrades.error} onRetry={() => void botTrades.refetch()} />
        </div>
      )}

      {!isLoading && rows.length === 0 && (
        <p className="p-6 text-center text-xs text-muted-foreground">
          No trades yet — the bots are waiting for setups that pass their filters.
        </p>
      )}

      {rows.length > 0 && (
        <div className="max-h-[28rem] overflow-auto">
          <table className="w-full min-w-[760px] font-mono text-xs">
            <thead className="sticky top-0 z-10 bg-card">
              <tr className="border-b text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-2 py-2 font-medium">Bot</th>
                <th className="px-2 py-2 font-medium">Token</th>
                <th className="px-2 py-2 text-right font-medium">Size</th>
                <th className="px-2 py-2 text-right font-medium">Entry</th>
                <th className="px-2 py-2 text-right font-medium">Exit</th>
                <th className="px-2 py-2 text-right font-medium">PnL</th>
                <th className="px-4 py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const win = (r.pnlUsd ?? 0) > 0;
                return (
                  <tr
                    key={r.key}
                    className="border-b border-border/50 last:border-0 hover:bg-muted/40"
                  >
                    <td className="whitespace-nowrap px-4 py-1.5 tabular-nums text-muted-foreground">
                      {clock(r.ts)}
                    </td>
                    <td className={cn("px-2 py-1.5 uppercase", SOURCE_TONE[r.source])}>
                      {r.source}
                    </td>
                    <td className="px-2 py-1.5 font-medium">{r.symbol}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      ${r.size.toFixed(0)}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {formatPrice(r.entry)}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {r.exit === null ? (
                        <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase text-primary">
                          open
                        </span>
                      ) : (
                        formatPrice(r.exit)
                      )}
                    </td>
                    <td
                      className={cn(
                        "px-2 py-1.5 text-right tabular-nums",
                        r.pnlUsd === null
                          ? "text-muted-foreground"
                          : win
                            ? "text-emerald-400"
                            : "text-red-400",
                      )}
                    >
                      {r.pnlUsd === null
                        ? "—"
                        : `${win ? "+" : ""}$${r.pnlUsd.toFixed(2)} (${r.pnlPct?.toFixed(1)}%)`}
                    </td>
                    <td
                      className="max-w-[320px] truncate px-4 py-1.5 text-muted-foreground"
                      title={r.note}
                    >
                      {r.note || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
