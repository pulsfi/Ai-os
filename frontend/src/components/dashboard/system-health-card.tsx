"use client";

/** Live system health: overall status + one row per backend component
 *  (api, database, redis, solana_rpc) with probe latency. GET /health, 15s. */
import { Activity } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealth, useSystemInfo } from "@/hooks/use-backend";
import { StatusPill } from "./status-pill";
import { WidgetError } from "./widget-error";

export function SystemHealthCard() {
  const health = useHealth();
  const info = useSystemInfo();

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Activity className="size-4 text-primary" /> System Health
        </CardTitle>
        {health.data && <StatusPill status={health.data.status} />}
      </CardHeader>
      <CardContent>
        {health.isPending ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : health.isError ? (
          <WidgetError error={health.error} onRetry={() => health.refetch()} />
        ) : (
          <ul className="space-y-1.5">
            {health.data.components.map((c) => (
              <li
                key={c.name}
                className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-1.5"
              >
                <span className="font-mono text-xs">{c.name}</span>
                <span className="flex items-center gap-2">
                  {c.latency_ms != null && (
                    <span className="text-[11px] text-muted-foreground">
                      {Math.round(c.latency_ms)}ms
                    </span>
                  )}
                  <StatusPill status={c.status} />
                </span>
              </li>
            ))}
          </ul>
        )}
        {info.data && (
          <p className="mt-3 text-[11px] text-muted-foreground">
            {info.data.app_name} v{info.data.version} · {info.data.environment}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
