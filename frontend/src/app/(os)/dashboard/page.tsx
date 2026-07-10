"use client";

/**
 * Command center — an institutional terminal layout:
 *   KPI rail  →  chart + AI decision  →  activity feed
 * Every tile reads live backend data; nothing is mocked. Panels degrade
 * independently (skeleton → data | inline error).
 */
import * as React from "react";
import {
  Activity,
  Cpu,
  Gauge,
  Layers,
  Radar,
  ShieldCheck,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { AlertsCard } from "@/components/dashboard/alerts-card";
import { KpiTile } from "@/components/terminal-ui/kpi-tile";
import { DecisionCard } from "@/components/terminal-ui/decision-card";
import { TokenChart } from "@/components/terminal-ui/token-chart";
import {
  useAgentRuntime,
  useBotPerformance,
  useExecutionStatus,
  useMarketTokens,
  usePumpfunNew,
} from "@/hooks/use-backend";
import { useFleetLive } from "@/hooks/use-fleet-live";
import { formatInt, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const tokens = useMarketTokens();
  const perf = useBotPerformance();
  const fleet = useFleetLive();
  const exec = useExecutionStatus();
  const runtime = useAgentRuntime();
  const launches = usePumpfunNew(12);

  const [mint, setMint] = React.useState("");
  // Default the chart/decision panels to the first watchlist token (SOL).
  const selected =
    tokens.data?.find((t) => t.mint === mint) ?? tokens.data?.[0];
  const activeMint = selected?.mint ?? "";

  const fleetPerf = perf.data?.find((p) => p.bot_id === "fleet");
  const running = fleet.bots?.filter((b) => b.state === "running").length ?? 0;
  const open = fleet.bots?.reduce((n, b) => n + b.open_positions, 0) ?? 0;
  const sol = tokens.data?.find((t) => (t.symbol ?? "").toUpperCase() === "SOL");
  const pnl = fleetPerf?.realized_pnl_usd;
  const mode = exec.data?.kill_switch ? "HALTED" : exec.data?.armed ? "LIVE" : "PAPER";

  return (
    <section className="space-y-3">
      {/* ---- KPI rail ---- */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
        <KpiTile
          label="Fleet PnL" icon={Wallet} loading={perf.isLoading}
          value={pnl === undefined ? "—" : `$${pnl.toFixed(2)}`}
          tone={pnl === undefined ? undefined : pnl >= 0 ? "up" : "down"}
          sub="paper (virtual)"
        />
        <KpiTile
          label="Win rate" icon={TrendingUp} loading={perf.isLoading}
          value={fleetPerf?.win_rate_pct == null ? "—" : `${fleetPerf.win_rate_pct}%`}
          sub={fleetPerf ? `${fleetPerf.closed_trades} closed` : undefined}
        />
        <KpiTile
          label="SOL" icon={Activity} loading={tokens.isLoading}
          value={formatPrice(sol?.price_usd)}
          tone={(sol?.change_24h ?? 0) >= 0 ? "up" : "down"}
          sub={sol?.change_24h != null ? `${sol.change_24h.toFixed(1)}% 24h` : undefined}
        />
        <KpiTile
          label="Active bots" icon={Cpu} loading={fleet.isLoading}
          value={fleet.bots ? `${running}/${fleet.bots.length}` : "—"}
          tone={running > 0 ? "up" : "warn"} sub={fleet.live ? "live socket" : "polling"}
        />
        <KpiTile
          label="AI pipeline" icon={Gauge} loading={runtime.isLoading}
          value={runtime.data ? (runtime.data.running ? "ON" : "OFF") : "—"}
          tone={runtime.data?.running ? "up" : "warn"}
          sub={runtime.data ? `${runtime.data.cycles} cycles` : undefined}
        />
        <KpiTile
          label="Open pos." icon={Layers} loading={fleet.isLoading}
          value={fleet.bots ? String(open) : "—"}
        />
        <KpiTile
          label="Mode" icon={ShieldCheck}
          value={mode} tone={mode === "PAPER" ? "up" : mode === "HALTED" ? "down" : "warn"}
          sub="risk posture"
        />
        <KpiTile
          label="New launches" icon={Radar} loading={launches.isLoading}
          value={launches.data ? formatInt(launches.data.length) : "—"} sub="pump.fun, live"
        />
      </div>

      {/* token selector */}
      <div className="flex flex-wrap gap-1.5">
        {tokens.data?.map((t) => (
          <button
            key={t.mint}
            type="button"
            onClick={() => setMint(t.mint)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              t.mint === activeMint
                ? "border-primary bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            {t.symbol ?? t.mint.slice(0, 4)}
          </button>
        ))}
      </div>

      {/* ---- chart + decision ---- */}
      <div className="grid gap-3 xl:grid-cols-[1fr_360px]">
        <div className="min-h-[20rem]">
          <TokenChart mint={activeMint} symbol={selected?.symbol ?? undefined} />
        </div>
        <div className="min-h-[20rem]">
          <DecisionCard mint={activeMint} symbol={selected?.symbol ?? undefined} />
        </div>
      </div>

      {/* ---- activity feed ---- */}
      <AlertsCard />
    </section>
  );
}
