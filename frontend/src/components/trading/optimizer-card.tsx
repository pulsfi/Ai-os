"use client";

/**
 * Adaptive optimizer — regime metrics, current mode, applied parameters,
 * and the cooling lock, live from /bots/optimizer. "Optimize now" runs a
 * pass immediately (it still refuses on insufficient data; force is
 * deliberately not exposed here — overriding the lock is an API-level,
 * explicit decision).
 */
import { Gauge, Lock, LockOpen, Sparkles } from "lucide-react";
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
import { useOptimizeNow, useOptimizer } from "@/hooks/use-backend";
import { timeAgo } from "@/lib/format";

const MODE_LABELS: Record<string, string> = {
  launch: "Launch sniping",
  momentum: "Momentum",
  scalping: "Scalping",
  consolidation: "Consolidation (defensive)",
};

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className="font-mono text-sm tabular-nums">{value}</p>
    </div>
  );
}

export function OptimizerCard() {
  const q = useOptimizer();
  const run = useOptimizeNow();

  function optimizeNow() {
    run.mutate(false, {
      onSuccess: (r) =>
        r.applied
          ? toast.success(`Optimizer applied ${r.mode} mode`)
          : toast.info(r.reason ?? "Optimizer made no change"),
      onError: (e) => toast.error(e instanceof Error ? e.message : "Optimizer failed"),
    });
  }

  const m = (q.data?.metrics ?? {}) as Record<string, number | null>;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="size-4 text-primary" /> Adaptive optimizer
            </CardTitle>
            <CardDescription>
              Measures the launch-market regime and retunes the sniper — entry
              threshold moves only to walk-forward validated values, then locks
              for a cooling period
            </CardDescription>
          </div>
          <Button size="sm" variant="outline" className="h-8" disabled={run.isPending} onClick={optimizeNow}>
            <Gauge className="size-3.5" /> {run.isPending ? "Running…" : "Optimize now"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {q.isLoading && <Skeleton className="h-24 rounded-lg" />}
        {q.isError && <WidgetError error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && (
          <>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge>{q.data.mode ? MODE_LABELS[q.data.mode] ?? q.data.mode : "not yet calibrated"}</Badge>
              {q.data.locked ? (
                <Badge variant="secondary" className="gap-1">
                  <Lock className="size-3" /> locked until{" "}
                  {q.data.locked_until ? timeAgo(q.data.locked_until) : "—"}
                </Badge>
              ) : (
                <Badge variant="outline" className="gap-1">
                  <LockOpen className="size-3" /> recalibration open
                </Badge>
              )}
              {q.data.last_applied_at && (
                <span className="text-xs text-muted-foreground">
                  last applied {timeAgo(q.data.last_applied_at)}
                </span>
              )}
            </div>

            {q.data.metrics && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                <Metric label="ATR (launch)" value={m.atr_pct != null ? `${m.atr_pct}%` : "—"} />
                <Metric label="BB width" value={m.bb_width != null ? String(m.bb_width) : "—"} />
                <Metric label="Rel. volume" value={m.relative_volume != null ? `${m.relative_volume}x` : "—"} />
                <Metric
                  label="Buy pressure"
                  value={m.buy_pressure != null ? `${Math.round(Number(m.buy_pressure) * 100)}%` : "—"}
                />
                <Metric
                  label="Liquidity (med)"
                  value={m.liquidity_usd != null ? `$${Number(m.liquidity_usd).toLocaleString()}` : "—"}
                />
              </div>
            )}

            {q.data.params && (
              <p className="text-xs text-muted-foreground">
                Applied:{" "}
                <span className="font-mono">
                  {Object.entries(q.data.params)
                    .map(([k, v]) => `${k}=${String(v)}`)
                    .join(" · ")}
                </span>
              </p>
            )}
            {q.data.threshold_note && (
              <p className="text-xs text-muted-foreground">{q.data.threshold_note}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
