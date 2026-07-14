"use client";

/**
 * Backtesting — capture-replay results over the recorded rolling window.
 *
 * Three cards: data coverage (can you trust a backtest yet?), the ranked
 * variant grid (strategy tester), and walk-forward validation (the
 * anti-overfitting gate). Only validated variants should be promoted to
 * live paper trading — unvalidated winners are in-sample mirages.
 */
import { BadgeCheck, Database, GitCompareArrows, ShieldAlert } from "lucide-react";

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
import {
  useBacktestCoverage,
  useBacktestRank,
  useWalkForward,
} from "@/hooks/use-backend";
import { cn } from "@/lib/utils";

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className="font-mono text-lg tabular-nums">{value}</p>
    </div>
  );
}

export function CoverageCard() {
  const q = useBacktestCoverage();
  const enough = (q.data?.evaluated_launches ?? 0) >= 24;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Database className="size-4 text-primary" /> Recorded window
        </CardTitle>
        <CardDescription>
          Backtests replay what the system actually observed — real launches,
          real price paths, rolling ~5 days. No purchased or synthetic history.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {q.isLoading && <Skeleton className="h-16 rounded-lg" />}
        {q.isError && <WidgetError error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Tile label="Launches evaluated" value={String(q.data.evaluated_launches)} />
              <Tile label="Price samples" value={String(q.data.samples)} />
              <Tile label="Mints sampled" value={String(q.data.sampled_mints)} />
              <Tile label="Window" value={`${q.data.window_hours}h`} />
            </div>
            {!enough && (
              <p className="text-xs text-amber-400">
                Recorder is still accumulating (needs ~24+ evaluated launches for a
                meaningful walk-forward). It fills automatically while the sniper runs.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function num(v: number | null | undefined, digits = 2, prefix = ""): string {
  return v == null ? "—" : `${prefix}${v.toFixed(digits)}`;
}

export function RankingCard() {
  const q = useBacktestRank();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <GitCompareArrows className="size-4 text-primary" /> Strategy ranking
        </CardTitle>
        <CardDescription>
          Exit-mode × threshold grid replayed over the window, ranked by
          expectancy. Only ✓ validated variants (walk-forward) should go live.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {q.isLoading && <Skeleton className="h-40 rounded-lg" />}
        {q.isError && <WidgetError error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-xs">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Variant</th>
                  <th className="py-2 pr-3 text-right font-medium">Trades</th>
                  <th className="py-2 pr-3 text-right font-medium">Net</th>
                  <th className="py-2 pr-3 text-right font-medium">PF</th>
                  <th className="py-2 pr-3 text-right font-medium">Win rate</th>
                  <th className="py-2 pr-3 text-right font-medium">Sharpe</th>
                  <th className="py-2 pr-3 text-right font-medium">Max DD</th>
                  <th className="py-2 pr-3 text-right font-medium">Expectancy</th>
                  <th className="py-2 text-right font-medium">Validated</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((v) => (
                  <tr key={v.variant} className="border-b last:border-0">
                    <td className="py-2 pr-3 font-mono">
                      {v.exit_mode} @ {v.threshold}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono">{v.trades}</td>
                    <td
                      className={cn(
                        "py-2 pr-3 text-right font-mono",
                        v.net_profit_usd > 0 && "text-emerald-400",
                        v.net_profit_usd < 0 && "text-red-400",
                      )}
                    >
                      {num(v.net_profit_usd, 2, "$")}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono">{num(v.profit_factor)}</td>
                    <td className="py-2 pr-3 text-right font-mono">
                      {v.win_rate_pct == null ? "—" : `${v.win_rate_pct}%`}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono">{num(v.sharpe)}</td>
                    <td className="py-2 pr-3 text-right font-mono">
                      {num(v.max_drawdown_usd, 2, "$")}
                    </td>
                    <td
                      className={cn(
                        "py-2 pr-3 text-right font-mono",
                        (v.expectancy_usd ?? 0) > 0 && "text-emerald-400",
                        (v.expectancy_usd ?? 0) < 0 && "text-red-400",
                      )}
                    >
                      {num(v.expectancy_usd, 2, "$")}
                    </td>
                    <td className="py-2 text-right">
                      {v.validated ? (
                        <Badge className="gap-1"><BadgeCheck className="size-3" /> yes</Badge>
                      ) : (
                        <Badge variant="secondary">no</Badge>
                      )}
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

export function WalkForwardCard({ exitMode }: { exitMode: "fixed" | "capture" }) {
  const q = useWalkForward(exitMode);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldAlert className="size-4 text-primary" /> Walk-forward · {exitMode} exits
        </CardTitle>
        <CardDescription>
          Chronological train/test folds: the threshold is chosen on past data
          and judged on unseen data. This verdict decides promotion.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {q.isLoading && <Skeleton className="h-24 rounded-lg" />}
        {q.isError && <WidgetError error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && (
          <>
            <div className="flex items-center gap-2">
              {q.data.validated ? (
                <Badge className="gap-1"><BadgeCheck className="size-3" /> VALIDATED</Badge>
              ) : (
                <Badge variant="destructive">not validated</Badge>
              )}
              {q.data.reason && (
                <span className="text-xs text-muted-foreground">{q.data.reason}</span>
              )}
            </div>
            {q.data.folds.length > 0 && (
              <div className="space-y-1.5">
                {q.data.folds.map((f, i) => {
                  const oos = f.out_of_sample as
                    | { trades?: number; expectancy_usd?: number | null; profit_factor?: number | null }
                    | undefined;
                  return (
                    <div key={i} className="rounded-lg border px-3 py-2 text-xs">
                      <span className="font-medium">Fold {String(f.fold)}</span>
                      {oos ? (
                        <span className="ml-2 font-mono text-muted-foreground">
                          threshold {String(f.chosen_threshold)} · OOS {oos.trades ?? 0} trades ·
                          expectancy {oos.expectancy_usd == null ? "—" : `$${oos.expectancy_usd}`} ·
                          PF {oos.profit_factor ?? "—"}
                        </span>
                      ) : (
                        <span className="ml-2 text-muted-foreground">{String(f.reason ?? "")}</span>
                      )}
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
