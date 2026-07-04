"use client";

/**
 * Bot fleet — the multi-bot paper-trading runtime, live from /bots.
 *
 * Unlike the vault agents, these controls are REAL: start/stop/restart
 * change actual asyncio loops in the backend. Everything is paper mode
 * (virtual USD) until the roadmap's live-execution gate opens.
 */
import * as React from "react";
import {
  Activity,
  AlertTriangle,
  Cpu,
  Play,
  RotateCcw,
  ScrollText,
  Square,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useBots, useBotControl, useBotTrades } from "@/hooks/use-backend";
import { formatPct, formatPrice, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BotStatus } from "@/lib/api/schemas";

function StateBadge({ state }: { state: BotStatus["state"] }) {
  if (state === "running") {
    return (
      <Badge className="gap-1.5">
        <span className="relative flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />
          <span className="relative inline-flex size-2 rounded-full bg-current" />
        </span>
        running
      </Badge>
    );
  }
  if (state === "error") {
    return (
      <Badge variant="destructive" className="gap-1">
        <AlertTriangle className="size-3" /> error
      </Badge>
    );
  }
  return <Badge variant="secondary">stopped</Badge>;
}

export function BotFleetCard() {
  const bots = useBots();
  const control = useBotControl();
  const [logsFor, setLogsFor] = React.useState<string | null>(null);

  function act(botId: string, action: "start" | "stop" | "restart") {
    control.mutate(
      { botId, action },
      {
        onSuccess: (res) =>
          res.accepted
            ? toast.success(`${res.bot_id}: ${res.detail}`)
            : toast.info(`${res.bot_id}: ${res.detail}`),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Bot control failed"),
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Cpu className="size-4 text-primary" /> Bot fleet
            </CardTitle>
            <CardDescription>
              Live multi-bot runtime — paper mode (virtual ${""}
              {bots.data?.[0]?.config.usd_per_trade ?? 50} per trade), real controls
            </CardDescription>
          </div>
          {bots.data && (
            <Badge variant="outline" className="font-mono">
              {bots.data.filter((b) => b.state === "running").length}/{bots.data.length}{" "}
              running
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {bots.isLoading && (
          <div className="grid gap-3 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-44 rounded-xl" />
            ))}
          </div>
        )}
        {bots.isError && (
          <WidgetError error={bots.error} onRetry={() => void bots.refetch()} />
        )}
        {bots.data && (
          <div className="grid gap-3 lg:grid-cols-3">
            {bots.data.map((bot) => (
              <div key={bot.config.id} className="flex flex-col rounded-xl border p-4">
                <div className="mb-1 flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold">{bot.config.name}</p>
                  <StateBadge state={bot.state} />
                </div>
                <p className="mb-3 line-clamp-2 min-h-8 text-xs text-muted-foreground">
                  {bot.config.description}
                </p>

                <div className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  <span className="text-muted-foreground">Open</span>
                  <span className="text-right font-mono">{bot.open_positions}</span>
                  <span className="text-muted-foreground">Closed</span>
                  <span className="text-right font-mono">{bot.closed_trades}</span>
                  <span className="text-muted-foreground">Realized PnL</span>
                  <span
                    className={cn(
                      "text-right font-mono",
                      bot.realized_pnl_usd > 0 && "text-emerald-400",
                      bot.realized_pnl_usd < 0 && "text-red-400",
                    )}
                  >
                    ${bot.realized_pnl_usd.toFixed(2)}
                  </span>
                  <span className="text-muted-foreground">Win rate</span>
                  <span className="text-right font-mono">
                    {bot.win_rate_pct === null ? "—" : `${bot.win_rate_pct}%`}
                  </span>
                  <span className="text-muted-foreground">Ticks / errors</span>
                  <span className="text-right font-mono">
                    {bot.ticks} / {bot.errors}
                  </span>
                </div>

                {bot.last_error && (
                  <p className="mb-2 line-clamp-1 text-[10px] text-destructive">
                    {bot.last_error}
                  </p>
                )}

                <div className="mt-auto flex items-center gap-1.5">
                  {bot.state === "running" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8"
                      disabled={control.isPending}
                      onClick={() => act(bot.config.id, "stop")}
                    >
                      <Square className="size-3.5" /> Stop
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      className="h-8"
                      disabled={control.isPending}
                      onClick={() => act(bot.config.id, "start")}
                    >
                      <Play className="size-3.5" /> Start
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8"
                    disabled={control.isPending}
                    onClick={() => act(bot.config.id, "restart")}
                  >
                    <RotateCcw className="size-3.5" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="ml-auto h-8"
                    onClick={() => setLogsFor(bot.config.id)}
                  >
                    <ScrollText className="size-3.5" /> Trades
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <BotTradesSheet botId={logsFor} onClose={() => setLogsFor(null)} />
    </Card>
  );
}

function BotTradesSheet({ botId, onClose }: { botId: string | null; onClose: () => void }) {
  const trades = useBotTrades(botId);

  return (
    <Sheet open={botId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-hidden sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="font-mono">{botId}</SheetTitle>
          <SheetDescription>Paper trade log, newest first (live ledger)</SheetDescription>
        </SheetHeader>
        <ScrollArea className="h-[calc(100dvh-7rem)] pr-4">
          <div className="space-y-2 px-4 pb-8">
            {trades.isLoading && <Skeleton className="h-24 rounded-lg" />}
            {trades.isError && (
              <p className="text-xs text-destructive">Could not load trades.</p>
            )}
            {trades.data?.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No trades yet — the bot is waiting for a setup that passes its filters.
              </p>
            )}
            {trades.data?.map((t) => (
              <div key={t.id} className="rounded-lg border p-3 text-xs">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="font-medium">{t.symbol}</span>
                  <div className="flex items-center gap-2">
                    {t.pnl_pct !== null && (
                      <span
                        className={cn(
                          "font-mono",
                          (t.pnl_usd ?? 0) >= 0 ? "text-emerald-400" : "text-red-400",
                        )}
                      >
                        {formatPct(t.pnl_pct)} (${(t.pnl_usd ?? 0).toFixed(2)})
                      </span>
                    )}
                    <Badge variant={t.status === "open" ? "default" : "outline"}>
                      {t.status}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2 font-mono text-muted-foreground">
                  <Activity className="size-3" />
                  <span>
                    in {formatPrice(t.entry_price)} {timeAgo(t.entry_ts)}
                    {t.exit_price !== null && <> → out {formatPrice(t.exit_price)}</>}
                  </span>
                </div>
                {t.entry_note && (
                  <p className="mt-1 text-muted-foreground">{t.entry_note}</p>
                )}
                {t.exit_note && (
                  <p className="mt-0.5 text-muted-foreground">exit: {t.exit_note}</p>
                )}
              </div>
            ))}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
