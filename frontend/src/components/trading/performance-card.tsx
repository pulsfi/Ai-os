"use client";

/**
 * Performance review — the fleet's paper track record from
 * /bots/performance: equity curve (cumulative REALIZED PnL; unrealized
 * gains never flatter the chart) and a per-strategy comparison table.
 *
 * The curve is a dependency-free inline SVG: at this data volume a chart
 * library would be pure weight.
 */
import * as React from "react";
import { RotateCcw, TrendingUp } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useBotPerformance, useResetLedger } from "@/hooks/use-backend";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BotPerformance } from "@/lib/api/schemas";

function ResetButton() {
  const reset = useResetLedger();
  function confirmReset() {
    toast.warning("Wipe the paper track record?", {
      description: "Paper data only — starts a clean record under honest pricing.",
      action: {
        label: "Reset",
        onClick: () =>
          reset.mutate(undefined, {
            onSuccess: (r) => toast.success(r.detail),
            onError: () => toast.error("Reset failed"),
          }),
      },
      duration: 8000,
    });
  }
  return (
    <Button
      size="sm"
      variant="outline"
      className="h-8"
      disabled={reset.isPending}
      onClick={confirmReset}
    >
      <RotateCcw className="size-3.5" /> Reset record
    </Button>
  );
}

const W = 720;
const H = 160;
const PAD = 8;

function EquityCurve({ perf }: { perf: BotPerformance }) {
  if (perf.curve.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-xs text-muted-foreground">
        No closed trades yet — the curve starts with the first realized exit.
      </div>
    );
  }
  // Start every curve at 0 so the first trade reads as a move, not a dot.
  const values = [0, ...perf.curve.map((p) => p.equity_usd)];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = (W - PAD * 2) / (values.length - 1 || 1);
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - PAD * 2);
  const points = values.map((v, i) => `${PAD + i * stepX},${y(v).toFixed(1)}`);
  const final = values[values.length - 1];
  const zeroY = y(0);

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-40 w-full min-w-[420px]"
        role="img"
        aria-label={`Equity curve for ${perf.name}: ${final >= 0 ? "+" : ""}$${final.toFixed(2)} over ${perf.closed_trades} closed trades`}
      >
        {/* zero line */}
        <line
          x1={PAD}
          x2={W - PAD}
          y1={zeroY}
          y2={zeroY}
          className="stroke-border"
          strokeDasharray="4 4"
          strokeWidth="1"
        />
        {/* area fill down to zero */}
        <polygon
          points={`${PAD},${zeroY} ${points.join(" ")} ${W - PAD},${zeroY}`}
          className={cn(
            "opacity-15",
            final >= 0 ? "fill-emerald-400" : "fill-red-400",
          )}
        />
        <polyline
          points={points.join(" ")}
          fill="none"
          strokeWidth="2"
          className={cn(final >= 0 ? "stroke-emerald-400" : "stroke-red-400")}
        />
      </svg>
    </div>
  );
}

export function PerformanceCard() {
  const perf = useBotPerformance();
  const [selected, setSelected] = React.useState("fleet");

  const current = perf.data?.find((p) => p.bot_id === selected) ?? perf.data?.[0];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="size-4 text-primary" /> Performance review
            </CardTitle>
            <CardDescription>
              Realized-PnL equity curve and per-strategy track record — the evidence
              the live-execution gate will be judged on
            </CardDescription>
          </div>
          <ResetButton />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {perf.isLoading && <Skeleton className="h-64 rounded-lg" />}
        {perf.isError && (
          <WidgetError error={perf.error} onRetry={() => void perf.refetch()} />
        )}
        {perf.data && current && (
          <>
            <div className="flex flex-wrap gap-1.5">
              {perf.data.map((p) => (
                <button
                  key={p.bot_id}
                  type="button"
                  onClick={() => setSelected(p.bot_id)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs transition-colors",
                    p.bot_id === current.bot_id
                      ? "border-primary bg-primary/15 text-primary"
                      : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  {p.name}
                  <span
                    className={cn(
                      "ml-1.5 font-mono",
                      p.realized_pnl_usd > 0 && "text-emerald-400",
                      p.realized_pnl_usd < 0 && "text-red-400",
                    )}
                  >
                    ${p.realized_pnl_usd.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>

            <EquityCurve perf={current} />

            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-xs">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Strategy</th>
                    <th className="py-2 pr-3 text-right font-medium">Closed</th>
                    <th className="py-2 pr-3 text-right font-medium">W / L</th>
                    <th className="py-2 pr-3 text-right font-medium">Win rate</th>
                    <th className="py-2 pr-3 text-right font-medium">Realized PnL</th>
                    <th className="py-2 pr-3 text-right font-medium">Avg trade</th>
                    <th className="py-2 text-right font-medium">Best / Worst</th>
                  </tr>
                </thead>
                <tbody>
                  {perf.data.map((p) => (
                    <tr key={p.bot_id} className="border-b last:border-0">
                      <td className="py-2 pr-3">
                        {p.name}
                        {p.bot_id === "fleet" && (
                          <Badge variant="outline" className="ml-1.5 text-[10px]">
                            total
                          </Badge>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">{p.closed_trades}</td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {p.wins} / {p.losses}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {p.win_rate_pct === null ? "—" : `${p.win_rate_pct}%`}
                      </td>
                      <td
                        className={cn(
                          "py-2 pr-3 text-right font-mono",
                          p.realized_pnl_usd > 0 && "text-emerald-400",
                          p.realized_pnl_usd < 0 && "text-red-400",
                        )}
                      >
                        ${p.realized_pnl_usd.toFixed(2)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {formatPct(p.avg_pnl_pct)}
                      </td>
                      <td className="py-2 text-right font-mono">
                        <span className="text-emerald-400">{formatPct(p.best_trade_pct)}</span>
                        {" / "}
                        <span className="text-red-400">{formatPct(p.worst_trade_pct)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
