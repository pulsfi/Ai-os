"use client";

/** Top movers — /market/trending ranked by 24h change (live, multi-provider). */
import { TrendingDown, TrendingUp } from "lucide-react";

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
import { useMarketTrending } from "@/hooks/use-backend";
import { formatMoney, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

export function TrendingCard() {
  const trending = useMarketTrending();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Trending</CardTitle>
        <CardDescription>Tracked tokens ranked by 24h change</CardDescription>
      </CardHeader>
      <CardContent>
        {trending.isLoading && (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 rounded-lg" />
            ))}
          </div>
        )}
        {trending.isError && (
          <WidgetError error={trending.error} onRetry={() => void trending.refetch()} />
        )}
        {trending.data && (
          <div className="space-y-2">
            {trending.data.map((t, i) => {
              const up = (t.change_24h ?? 0) >= 0;
              return (
                <div
                  key={t.mint}
                  className="flex items-center justify-between gap-3 rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-5 text-center font-mono text-xs text-muted-foreground">
                      {i + 1}
                    </span>
                    <div>
                      <p className="text-sm font-medium">{t.symbol ?? t.mint.slice(0, 6)}</p>
                      <p className="text-xs text-muted-foreground">
                        vol {formatMoney(t.volume_24h)} · liq {formatMoney(t.liquidity_usd)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm">{formatPrice(t.price_usd)}</span>
                    <Badge
                      variant="outline"
                      className={cn(
                        "gap-1 font-mono",
                        up ? "text-emerald-400" : "text-red-400",
                      )}
                    >
                      {up ? (
                        <TrendingUp className="size-3" />
                      ) : (
                        <TrendingDown className="size-3" />
                      )}
                      {formatPct(t.change_24h)}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
