"use client";

/**
 * Fleet risk — live from /bots/risk: open exposure vs the cap, today's
 * realized PnL vs the daily loss limit, worst case if every stop fires,
 * and per-symbol concentration. When a circuit breaker is active it says
 * so in plain words.
 */
import { ShieldCheck, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { usePortfolioRisk } from "@/hooks/use-backend";
import { cn } from "@/lib/utils";

function Meter({ label, used, cap }: { label: string; used: number; cap: number }) {
  const pct = cap > 0 ? Math.min(100, (used / cap) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono tabular-nums">
          ${used.toFixed(2)} / ${cap.toFixed(0)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            pct >= 90 ? "bg-red-400" : pct >= 60 ? "bg-amber-400" : "bg-emerald-400",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function RiskCard() {
  const q = usePortfolioRisk();
  const r = q.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {r?.entries_blocked ? (
            <ShieldAlert className="size-4 text-red-400" />
          ) : (
            <ShieldCheck className="size-4 text-primary" />
          )}
          Fleet risk
        </CardTitle>
        <CardDescription>
          Exposure cap, daily loss budget, and worst case if every stop fires
          — the circuit breakers behind every new entry
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {q.isLoading && <Skeleton className="h-24 rounded-lg" />}
        {q.isError && <WidgetError error={q.error} onRetry={() => void q.refetch()} />}
        {r && (
          <>
            {r.entries_blocked && (
              <Badge variant="destructive" className="whitespace-normal">
                {r.entries_blocked}
              </Badge>
            )}
            <Meter label={`Open exposure (${r.open_positions} positions)`}
                   used={r.open_exposure_usd} cap={r.max_exposure_usd} />
            <Meter label="Daily loss budget used"
                   used={Math.max(0, -r.today_pnl_usd)} cap={r.daily_loss_limit_usd} />
            <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
              <div className="rounded-lg border bg-muted/30 px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Today PnL</p>
                <p className={cn("font-mono", r.today_pnl_usd >= 0 ? "text-emerald-400" : "text-red-400")}>
                  {r.today_pnl_usd >= 0 ? "+" : ""}${r.today_pnl_usd.toFixed(2)}
                </p>
              </div>
              <div className="rounded-lg border bg-muted/30 px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Budget left</p>
                <p className="font-mono">${r.daily_budget_left_usd.toFixed(2)}</p>
              </div>
              <div className="rounded-lg border bg-muted/30 px-2.5 py-2" title="Sum of size × stop distance; gap-throughs can exceed it">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Risk at stops</p>
                <p className="font-mono">${r.risk_at_stop_usd.toFixed(2)}</p>
              </div>
            </div>
            {Object.keys(r.exposure_by_symbol).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(r.exposure_by_symbol).map(([sym, usd]) => (
                  <Badge key={sym} variant="outline" className="font-normal">
                    {sym} <span className="ml-1 font-mono text-primary">${usd.toFixed(0)}</span>
                  </Badge>
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
