"use client";

/** Market watchlist: merged multi-provider data per tracked token, with the
 *  cross-provider divergence warning surfaced. GET /market/tokens, 30s. */
import { AlertTriangle, LineChart } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useMarketTokens } from "@/hooks/use-backend";
import { formatMoney, formatPct, formatPrice, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import { WidgetError } from "./widget-error";

export function WatchlistCard() {
  const tokens = useMarketTokens();

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <LineChart className="size-4 text-primary" /> Market Watchlist
        </CardTitle>
        {tokens.data?.[0] && (
          <span className="text-[11px] text-muted-foreground">
            updated {timeAgo(tokens.data[0].fetched_at)}
          </span>
        )}
      </CardHeader>
      <CardContent>
        {tokens.isPending ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : tokens.isError ? (
          <WidgetError error={tokens.error} onRetry={() => tokens.refetch()} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 pr-3 font-medium">Token</th>
                  <th className="pb-2 pr-3 font-medium">Price</th>
                  <th className="pb-2 pr-3 font-medium">24h</th>
                  <th className="pb-2 pr-3 font-medium">Liquidity</th>
                  <th className="pb-2 pr-3 font-medium">Volume 24h</th>
                  <th className="pb-2 font-medium">Sources</th>
                </tr>
              </thead>
              <tbody>
                {tokens.data.map((t) => (
                  <tr key={t.mint} className="border-b border-border/50 last:border-0">
                    <td className="py-2.5 pr-3 font-medium">
                      {t.symbol ?? `${t.mint.slice(0, 6)}…`}
                    </td>
                    <td className="py-2.5 pr-3 font-mono">{formatPrice(t.price_usd)}</td>
                    <td
                      className={cn(
                        "py-2.5 pr-3 font-mono",
                        (t.change_24h ?? 0) >= 0 ? "text-success" : "text-destructive",
                      )}
                    >
                      {formatPct(t.change_24h)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono">{formatMoney(t.liquidity_usd)}</td>
                    <td className="py-2.5 pr-3 font-mono">{formatMoney(t.volume_24h)}</td>
                    <td className="py-2.5">
                      <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        {t.sources.length}
                        {t.divergence_pct != null && t.divergence_pct > 2 && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <AlertTriangle className="size-3.5 text-warning" />
                            </TooltipTrigger>
                            <TooltipContent>
                              Providers disagree by {t.divergence_pct}%
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
