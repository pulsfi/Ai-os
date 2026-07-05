"use client";

/**
 * Terminal ticker — one thin strip with everything that matters:
 * fleet equity, record, open positions, SOL price, chain slot, and the
 * live-socket state. All real data; every cell degrades to "—" honestly.
 */
import { Activity, Radio } from "lucide-react";

import { useBotPerformance, useChainStatus, useMarketTokens } from "@/hooks/use-backend";
import { useFleetLive } from "@/hooks/use-fleet-live";
import { formatInt, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

function Cell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "up" | "down";
}) {
  return (
    <div className="flex shrink-0 items-baseline gap-1.5 px-3 first:pl-0">
      <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "font-mono text-xs font-medium tabular-nums",
          tone === "up" && "text-emerald-400",
          tone === "down" && "text-red-400",
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function TickerBar() {
  const fleet = useFleetLive();
  const perf = useBotPerformance();
  const tokens = useMarketTokens();
  const chain = useChainStatus();

  const fleetPerf = perf.data?.find((p) => p.bot_id === "fleet");
  const running = fleet.bots?.filter((b) => b.state === "running").length;
  const openPositions = fleet.bots?.reduce((n, b) => n + b.open_positions, 0);
  const sol = tokens.data?.find((t) => t.symbol?.toUpperCase() === "SOL");
  const pnl = fleetPerf?.realized_pnl_usd;

  return (
    <div className="flex items-center overflow-x-auto rounded-lg border bg-card/80 px-3 py-2 [scrollbar-width:none]">
      <div
        className={cn(
          "mr-2 flex shrink-0 items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest",
          fleet.live
            ? "bg-emerald-500/15 text-emerald-400"
            : "bg-muted text-muted-foreground",
        )}
      >
        <Radio className="size-3" />
        {fleet.live ? "live" : "poll"}
      </div>

      <div className="flex divide-x divide-border">
        <Cell
          label="Equity"
          value={pnl === undefined ? "—" : `$${pnl.toFixed(2)}`}
          tone={pnl === undefined ? undefined : pnl >= 0 ? "up" : "down"}
        />
        <Cell
          label="Record"
          value={
            fleetPerf ? `${fleetPerf.wins}W/${fleetPerf.losses}L` : "—"
          }
        />
        <Cell
          label="Win"
          value={
            fleetPerf?.win_rate_pct == null ? "—" : `${fleetPerf.win_rate_pct}%`
          }
        />
        <Cell label="Open" value={openPositions === undefined ? "—" : String(openPositions)} />
        <Cell
          label="Bots"
          value={running === undefined ? "—" : `${running}/${fleet.bots?.length ?? 0}`}
          tone={running ? "up" : undefined}
        />
        <Cell label="SOL" value={formatPrice(sol?.price_usd)} />
        <Cell label="Slot" value={chain.data?.slot == null ? "—" : formatInt(chain.data.slot)} />
        <div className="flex shrink-0 items-center gap-1 pl-3 text-[10px] uppercase tracking-widest text-muted-foreground">
          <Activity className="size-3 text-primary" />
          paper mode
        </div>
      </div>
    </div>
  );
}
