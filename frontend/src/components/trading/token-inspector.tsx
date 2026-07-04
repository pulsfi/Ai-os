"use client";

/**
 * Token inspector — /market/token/{address} (merged live data + on-chain
 * authorities) and /market/history/{address} (stored snapshots).
 *
 * History requires PostgreSQL; when it is not running the backend returns
 * an error and this card says so honestly instead of drawing a fake chart.
 */
import * as React from "react";
import { Search, ShieldAlert, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useMarketHistory, useMarketToken } from "@/hooks/use-backend";
import { ApiError } from "@/lib/api/client";
import { formatMoney, formatPct, formatPrice, timeAgo } from "@/lib/format";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono text-sm">{value}</p>
    </div>
  );
}

export function TokenInspector() {
  const [input, setInput] = React.useState("");
  const [address, setAddress] = React.useState("");
  const token = useMarketToken(address);
  const history = useMarketHistory(address, 50);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Token inspector</CardTitle>
        <CardDescription>
          Merged multi-provider market data + on-chain authorities for any mint
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setAddress(input.trim());
          }}
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Token mint address…"
            className="font-mono text-xs"
          />
          <Button type="submit" size="icon" disabled={!input.trim()}>
            <Search className="size-4" />
          </Button>
        </form>

        {token.isFetching && <Skeleton className="h-40 rounded-lg" />}

        {token.isError && !token.isFetching && (
          <WidgetError error={token.error} onRetry={() => void token.refetch()} />
        )}

        {token.data && !token.isFetching && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold">
                  {token.data.market.symbol ?? address.slice(0, 8)}
                </span>
                {token.data.authorities &&
                  (token.data.authorities.is_fully_revoked ? (
                    <Badge className="gap-1">
                      <ShieldCheck className="size-3" /> authorities revoked
                    </Badge>
                  ) : (
                    <Badge variant="destructive" className="gap-1">
                      <ShieldAlert className="size-3" /> authority active
                    </Badge>
                  ))}
              </div>
              <span className="text-xs text-muted-foreground">
                sources: {token.data.market.sources.join(", ") || "none"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <Stat label="Price" value={formatPrice(token.data.market.price_usd)} />
              <Stat label="24h change" value={formatPct(token.data.market.change_24h)} />
              <Stat label="24h volume" value={formatMoney(token.data.market.volume_24h)} />
              <Stat label="Liquidity" value={formatMoney(token.data.market.liquidity_usd)} />
              <Stat label="Market cap" value={formatMoney(token.data.market.market_cap)} />
              <Stat label="FDV" value={formatMoney(token.data.market.fdv)} />
            </div>

            {/* history — honest empty/error states, no fake chart */}
            <div className="rounded-lg border p-3">
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Stored history (PostgreSQL)
              </p>
              {history.isFetching && <Skeleton className="h-10 rounded" />}
              {history.isError && !history.isFetching && (
                <p className="text-xs text-muted-foreground">
                  {history.error instanceof ApiError
                    ? history.error.message
                    : "History unavailable."}{" "}
                  Snapshots are stored only while PostgreSQL and the market
                  scheduler are running.
                </p>
              )}
              {history.data && history.data.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No snapshots stored for this token yet.
                </p>
              )}
              {history.data && history.data.length > 0 && (
                <div className="max-h-44 space-y-1 overflow-y-auto">
                  {history.data.map((h) => (
                    <div
                      key={h.ts}
                      className="flex items-center justify-between font-mono text-xs"
                    >
                      <span className="text-muted-foreground">{timeAgo(h.ts)}</span>
                      <span>{formatPrice(h.price_usd)}</span>
                      <span>{formatPct(h.change_24h)}</span>
                      <span className="text-muted-foreground">
                        {formatMoney(h.volume_24h)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
