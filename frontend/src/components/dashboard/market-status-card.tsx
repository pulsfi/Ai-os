"use client";

/** Market Intelligence monitoring: provider availability + latency, cache
 *  hit rate, scheduler state. GET /market/status, 30s. */
import { Database } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMarketStatus } from "@/hooks/use-backend";
import { timeAgo } from "@/lib/format";
import { StatusPill } from "./status-pill";
import { WidgetError } from "./widget-error";

export function MarketStatusCard() {
  const status = useMarketStatus();

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Database className="size-4 text-primary" /> Data Providers
        </CardTitle>
        {status.data && (
          <span className="text-[11px] text-muted-foreground">
            cache: {status.data.cache_backend} · {status.data.cache_hits} hits
          </span>
        )}
      </CardHeader>
      <CardContent>
        {status.isPending ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : status.isError ? (
          <WidgetError error={status.error} onRetry={() => status.refetch()} />
        ) : (
          <>
            <ul className="space-y-1.5">
              {status.data.providers.map((p) => (
                <li
                  key={p.name}
                  className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-1.5"
                >
                  <span className="font-mono text-xs">{p.name}</span>
                  <span className="flex items-center gap-2">
                    {p.avg_latency_ms != null && (
                      <span className="text-[11px] text-muted-foreground">
                        {Math.round(p.avg_latency_ms)}ms
                      </span>
                    )}
                    {p.errors > 0 && (
                      <Badge variant="outline" className="h-5 text-[10px] text-warning">
                        {p.errors} err
                      </Badge>
                    )}
                    {!p.configured ? (
                      <Badge variant="outline" className="h-5 text-[10px]">
                        no key
                      </Badge>
                    ) : (
                      <StatusPill
                        status={p.errors > 0 && p.calls === p.errors ? "down" : "ok"}
                        label={p.calls > 0 ? `${p.calls} calls` : "idle"}
                      />
                    )}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[11px] text-muted-foreground">
              scheduler {status.data.scheduler_enabled ? "on" : "off"} ·{" "}
              {status.data.tracked_tokens} tokens tracked · last refresh{" "}
              {timeAgo(status.data.last_refresh)}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
