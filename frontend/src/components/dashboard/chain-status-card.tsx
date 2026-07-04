"use client";

/** Live Solana mainnet snapshot: slot, epoch progress, TPS.
 *  GET /solana/status, refreshed every 10s. */
import { Boxes } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useChainStatus } from "@/hooks/use-backend";
import { formatInt } from "@/lib/format";
import { StatusPill } from "./status-pill";
import { WidgetError } from "./widget-error";

export function ChainStatusCard() {
  const chain = useChainStatus();

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Boxes className="size-4 text-primary" /> Solana Mainnet
        </CardTitle>
        {chain.data && (
          <StatusPill
            status={chain.data.healthy ? "ok" : "down"}
            label={chain.data.healthy ? "healthy" : "unhealthy"}
          />
        )}
      </CardHeader>
      <CardContent>
        {chain.isPending ? (
          <div className="grid grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : chain.isError ? (
          <WidgetError error={chain.error} onRetry={() => chain.refetch()} />
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-[11px] text-muted-foreground">Slot</p>
              <p className="truncate font-mono text-sm font-semibold">
                {formatInt(chain.data.slot)}
              </p>
            </div>
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-[11px] text-muted-foreground">Epoch</p>
              <p className="font-mono text-sm font-semibold">
                {chain.data.epoch ? chain.data.epoch.epoch : "—"}
                {chain.data.epoch && (
                  <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                    {chain.data.epoch.progress_pct}%
                  </span>
                )}
              </p>
              {chain.data.epoch && (
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${chain.data.epoch.progress_pct}%` }}
                  />
                </div>
              )}
            </div>
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-[11px] text-muted-foreground">TPS</p>
              <p className="font-mono text-sm font-semibold">
                {formatInt(chain.data.tps)}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
