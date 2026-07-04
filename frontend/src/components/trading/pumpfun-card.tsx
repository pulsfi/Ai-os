"use client";

/**
 * Pump.fun discovery — live meme-coin launches from /market/pumpfun/*.
 * Two views: freshest launches and coins closest to graduating off the
 * bonding curve. Read-only discovery; no trading controls by design.
 */
import * as React from "react";
import { Flame, Rocket } from "lucide-react";

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
import { usePumpfunGraduating, usePumpfunNew } from "@/hooks/use-backend";
import { formatMoney, timeAgo } from "@/lib/format";
import type { PumpCoin } from "@/lib/api/schemas";

function CoinRow({ coin }: { coin: PumpCoin }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">
            {coin.symbol || coin.mint.slice(0, 6)}
          </span>
          {coin.is_currently_live && (
            <Badge variant="destructive" className="text-[10px]">live</Badge>
          )}
        </div>
        <p className="truncate text-xs text-muted-foreground">
          {coin.name} · {timeAgo(coin.created_at)}
          {coin.reply_count > 0 && ` · ${coin.reply_count} replies`}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="font-mono text-sm">{formatMoney(coin.usd_market_cap)}</p>
        <div className="mt-1 flex items-center justify-end gap-1.5">
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${coin.bonding_progress_pct}%` }}
            />
          </div>
          <span className="w-10 text-right font-mono text-[10px] text-muted-foreground">
            {coin.bonding_progress_pct.toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}

export function PumpFunCard() {
  const [view, setView] = React.useState<"new" | "graduating">("new");
  const fresh = usePumpfunNew(8);
  const graduating = usePumpfunGraduating(8);
  const active = view === "new" ? fresh : graduating;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">Pump.fun launches</CardTitle>
            <CardDescription>
              Live meme-coin discovery — bonding-curve progress toward graduation
            </CardDescription>
          </div>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant={view === "new" ? "secondary" : "ghost"}
              className="h-8"
              onClick={() => setView("new")}
            >
              <Rocket className="size-3.5" /> New
            </Button>
            <Button
              size="sm"
              variant={view === "graduating" ? "secondary" : "ghost"}
              className="h-8"
              onClick={() => setView("graduating")}
            >
              <Flame className="size-3.5" /> Graduating
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {active.isLoading && (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-lg" />
            ))}
          </div>
        )}
        {active.isError && (
          <WidgetError error={active.error} onRetry={() => void active.refetch()} />
        )}
        {active.data && (
          <div className="max-h-[26rem] space-y-2 overflow-y-auto pr-1">
            {active.data.map((coin) => (
              <CoinRow key={coin.mint} coin={coin} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
