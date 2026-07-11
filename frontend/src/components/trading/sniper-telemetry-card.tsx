"use client";

/**
 * Sniper signals funnel — live from /bots/telemetry. Answers "why is (or
 * isn't) it trading?" with evidence: every launch seen, every rejection
 * with its exact reason, everything executed, and the average confidence
 * across evaluated launches.
 */
import { Filter } from "lucide-react";

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
import { useSniperTelemetry } from "@/hooks/use-backend";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

const CATEGORY_LABELS: Record<string, string> = {
  weak_momentum: "weak momentum",
  few_buyers: "few buyers (bundle risk)",
  no_flow_data: "no buyer data",
  net_selling: "net selling",
  rug_risk: "rug risk (authority)",
  whale_concentration: "whale concentration",
  mcap_band: "mcap out of band",
  low_confidence: "low confidence",
  other: "other",
};

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</p>
      <p
        className={cn(
          "font-mono text-lg tabular-nums",
          tone === "up" && "text-emerald-400",
          tone === "down" && "text-red-400",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function SniperTelemetryCard() {
  const q = useSniperTelemetry();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Filter className="size-4 text-primary" /> Signals funnel
        </CardTitle>
        <CardDescription>
          Every launch the sniper evaluated — and the exact reason each reject
          was turned down (since the last restart)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {q.isLoading && <Skeleton className="h-40 rounded-lg" />}
        {q.isError && <WidgetError error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="Signals detected" value={String(q.data.signals_detected)} />
              <Stat label="Approved" value={String(q.data.signals_approved)} tone="up" />
              <Stat label="Trades executed" value={String(q.data.trades_executed)} tone="up" />
              <Stat
                label="Avg confidence"
                value={q.data.avg_confidence == null ? "—" : `${q.data.avg_confidence}/100`}
              />
            </div>

            {Object.keys(q.data.reject_reasons).length > 0 && (
              <div>
                <p className="mb-1.5 text-[10px] uppercase tracking-widest text-muted-foreground">
                  Rejections by reason (recent {q.data.rejected_recent})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(q.data.reject_reasons).map(([cat, n]) => (
                    <Badge key={cat} variant="outline" className="gap-1.5 font-normal">
                      {CATEGORY_LABELS[cat] ?? cat}
                      <span className="font-mono text-primary">{n}</span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {q.data.recent_rejections.length > 0 ? (
              <div className="max-h-64 space-y-1.5 overflow-y-auto">
                {q.data.recent_rejections.map((r) => (
                  <div
                    key={`${r.mint}-${r.ts}`}
                    className="rounded-lg border px-3 py-2 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{r.symbol}</span>
                      <span className="font-mono text-muted-foreground">
                        {r.score}/100 · {timeAgo(r.ts)}
                      </span>
                    </div>
                    <p className="mt-0.5 text-muted-foreground">{r.reasons.join("; ")}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No recent rejections recorded — either everything passed, or no
                launches have been evaluated since the last restart.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
