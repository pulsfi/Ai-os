"use client";

/**
 * AI Decision Card — runs the same confidence engine the sniper uses on a
 * selected token and shows the verdict: overall score, the factor meters,
 * hard-reject reasons, and the trade actions.
 *
 * Honesty: scores we can't measure (developer wallet history, social
 * signals) are shown as "no source" — never fabricated. Buy/Sell route to
 * the wallet where YOU approve every real trade; nothing auto-executes.
 */
import * as React from "react";
import Link from "next/link";
import { Ban, CheckCircle2, Info, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useTokenScore } from "@/hooks/use-backend";
import { ApiError } from "@/lib/api/client";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

function Meter({ label, points, max, detail }: { label: string; points: number; max: number; detail: string }) {
  const pct = max > 0 ? Math.round((points / max) * 100) : 0;
  const tone = pct >= 66 ? "bg-emerald-400" : pct >= 33 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-[11px]">
        <span className="font-medium capitalize">{label.replace("_", " ")}</span>
        <span className="font-mono text-muted-foreground">{detail}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** A score we have no real data source for — shown honestly, never faked. */
function NoSource({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-dashed px-2.5 py-1.5 text-[11px] text-muted-foreground">
      <span className="capitalize">{label}</span>
      <span className="inline-flex items-center gap-1">
        <Info className="size-3" /> no data source
      </span>
    </div>
  );
}

export function DecisionCard({ mint, symbol }: { mint: string; symbol?: string }) {
  const q = useTokenScore(mint);

  if (!mint) {
    return (
      <div className="flex h-full min-h-64 items-center justify-center rounded-xl border bg-card p-6 text-center text-sm text-muted-foreground">
        Select a token to run the AI decision engine.
      </div>
    );
  }

  const score = q.data?.score ?? 0;
  const ring = q.data?.approved ? "text-emerald-400" : "text-red-400";

  return (
    <div className="flex h-full flex-col rounded-xl border bg-card">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">AI Decision</p>
          <p className="font-mono text-sm font-medium">{symbol || `${mint.slice(0, 6)}…`}</p>
        </div>
        {q.data && (
          <Badge variant={q.data.approved ? "default" : "destructive"} className="gap-1">
            {q.data.approved ? <CheckCircle2 className="size-3" /> : <Ban className="size-3" />}
            {q.data.approved ? "ENTER" : "AVOID"}
          </Badge>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {q.isLoading && <Skeleton className="h-40 rounded-lg" />}
        {q.isError && !q.isLoading && (
          <WidgetError error={q.error} onRetry={() => void q.refetch()} />
        )}

        {q.data && (
          <>
            {/* overall confidence gauge */}
            <div className="flex items-center gap-4">
              <div className="relative flex size-20 shrink-0 items-center justify-center">
                <svg viewBox="0 0 36 36" className="size-20 -rotate-90">
                  <circle cx="18" cy="18" r="15.5" fill="none" className="stroke-muted" strokeWidth="3" />
                  <circle
                    cx="18" cy="18" r="15.5" fill="none"
                    className={cn("transition-all", ring)}
                    stroke="currentColor" strokeWidth="3" strokeLinecap="round"
                    strokeDasharray={`${(score / 100) * 97.4} 97.4`}
                  />
                </svg>
                <div className="absolute text-center">
                  <div className={cn("font-mono text-xl font-bold", ring)}>{score.toFixed(0)}</div>
                  <div className="text-[9px] uppercase text-muted-foreground">conf.</div>
                </div>
              </div>
              <div className="min-w-0 space-y-1 text-xs">
                <div className="flex items-center gap-1.5">
                  {q.data.mint_revoked === false || q.data.freeze_revoked === false ? (
                    <ShieldAlert className="size-4 text-red-400" />
                  ) : (
                    <ShieldCheck className="size-4 text-emerald-400" />
                  )}
                  <span className="text-muted-foreground">
                    mint {q.data.mint_revoked === null ? "?" : q.data.mint_revoked ? "revoked" : "ACTIVE"} ·
                    freeze {q.data.freeze_revoked === null ? "?" : q.data.freeze_revoked ? "revoked" : "ACTIVE"}
                  </span>
                </div>
                <p className="text-muted-foreground">
                  liq {formatMoney(q.data.liquidity_usd)} · mcap {formatMoney(q.data.market_cap)}
                </p>
                {q.data.buy_ratio_pct !== null && (
                  <p className="text-muted-foreground">
                    {q.data.buy_ratio_pct}% buys · {q.data.unique_wallets ?? 0} wallets
                  </p>
                )}
              </div>
            </div>

            {/* factor meters */}
            <div className="space-y-2.5">
              {q.data.factors.map((f) => (
                <Meter key={f.name} label={f.name} points={f.points} max={f.max_points} detail={f.detail} />
              ))}
            </div>

            {/* scores with no real data source — shown honestly */}
            <div className="space-y-1.5">
              <NoSource label="developer score" />
              <NoSource label="social score" />
            </div>

            {/* reject reasons */}
            {q.data.rejects.length > 0 && (
              <div className="space-y-1 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5">
                {q.data.rejects.map((r, i) => (
                  <p key={i} className="flex items-start gap-1.5 text-[11px] text-red-300">
                    <Ban className="mt-0.5 size-3 shrink-0" /> {r}
                  </p>
                ))}
              </div>
            )}

            {q.error instanceof ApiError && null}
          </>
        )}
      </div>

      {/* actions — real trades happen in the wallet, with your approval */}
      <div className="grid grid-cols-3 gap-2 border-t p-3">
        <Button asChild size="sm" className="bg-emerald-600 hover:bg-emerald-600/90">
          <Link href="/portfolio">Buy</Link>
        </Button>
        <Button asChild size="sm" variant="destructive">
          <Link href="/portfolio">Sell</Link>
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => toast.info("Bots trade this automatically in paper mode — see Automation.")}
        >
          Paper
        </Button>
      </div>
    </div>
  );
}
