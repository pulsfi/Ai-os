"use client";

/**
 * Paper trading ledger — the scalper's real track record from
 * /trading/summary + /trading/trades (read-only; the Node automation
 * layer is the writer). When no ledger exists yet the card says so.
 */
import { NotebookPen } from "lucide-react";

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
import { usePaperSummary, usePaperTrades } from "@/hooks/use-backend";
import { formatMoney, formatPct, formatPrice, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

function Kpi({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "font-mono text-sm",
          tone === "up" && "text-emerald-400",
          tone === "down" && "text-red-400",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function PaperLedgerCard() {
  const summary = usePaperSummary();
  const trades = usePaperTrades(20);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Paper trading ledger</CardTitle>
            <CardDescription>
              The scalper&apos;s hypothetical track record — no real funds
            </CardDescription>
          </div>
          <Badge variant="outline" className="gap-1">
            <NotebookPen className="size-3" /> paper mode
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {summary.isLoading && <Skeleton className="h-20 rounded-lg" />}
        {summary.isError && (
          <WidgetError error={summary.error} onRetry={() => void summary.refetch()} />
        )}

        {summary.data && !summary.data.available && (
          <p className="text-sm text-muted-foreground">
            No ledger yet — the paper scalper hasn&apos;t recorded any trades.
            Run the automation layer (<span className="font-mono">09 Automation</span>)
            to start building the track record that opens the live gate.
          </p>
        )}

        {summary.data?.available && (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Kpi
                label="Realized PnL"
                value={formatMoney(summary.data.realized_pnl_usd)}
                tone={summary.data.realized_pnl_usd >= 0 ? "up" : "down"}
              />
              <Kpi
                label="Win rate"
                value={
                  summary.data.win_rate_pct === null
                    ? "—"
                    : `${summary.data.win_rate_pct}%`
                }
              />
              <Kpi
                label="Trades"
                value={`${summary.data.total_trades} (${summary.data.open_trades} open)`}
              />
              <Kpi label="Snapshots" value={String(summary.data.snapshots_stored)} />
            </div>

            {trades.isLoading && <Skeleton className="h-24 rounded-lg" />}
            {trades.data && trades.data.length > 0 && (
              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {trades.data.map((t) => {
                  const up = (t.pnl_usd ?? 0) >= 0;
                  return (
                    <div
                      key={t.id}
                      className="flex items-center justify-between gap-3 rounded-lg border p-3"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{t.symbol}</span>
                          <Badge
                            variant={t.status === "open" ? "default" : "secondary"}
                            className="text-[10px]"
                          >
                            {t.status}
                          </Badge>
                        </div>
                        <p className="truncate text-xs text-muted-foreground">
                          {formatMoney(t.usd_size)} @ {formatPrice(t.entry_price)} ·{" "}
                          {timeAgo(t.entry_ts)}
                          {t.reasoning ? ` · ${t.reasoning}` : ""}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        {t.status === "closed" ? (
                          <>
                            <p
                              className={cn(
                                "font-mono text-sm",
                                up ? "text-emerald-400" : "text-red-400",
                              )}
                            >
                              {up ? "+" : ""}
                              {formatMoney(t.pnl_usd)}
                            </p>
                            <p className="font-mono text-[10px] text-muted-foreground">
                              {formatPct(t.pnl_pct)}
                            </p>
                          </>
                        ) : (
                          <p className="font-mono text-xs text-muted-foreground">
                            entry {formatPrice(t.entry_price)}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
