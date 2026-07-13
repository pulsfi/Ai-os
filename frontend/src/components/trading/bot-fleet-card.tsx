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
  Loader2,
  Play,
  RotateCcw,
  ScrollText,
  SlidersHorizontal,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Input } from "@/components/ui/input";
import { useBotControl, useBotTrades, useUpdateBotConfig } from "@/hooks/use-backend";
import { useFleetLive } from "@/hooks/use-fleet-live";
import { formatPct, formatPrice, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BotStatus, ProfitCapture } from "@/lib/api/schemas";

/** Mirrors the backend's default Dynamic Profit Capture ladder. */
const DEFAULT_PROFIT_CAPTURE: ProfitCapture = {
  enabled: false,
  tiers: [
    { gain_pct: 5, sell_pct: 10 }, { gain_pct: 10, sell_pct: 10 },
    { gain_pct: 25, sell_pct: 20 }, { gain_pct: 50, sell_pct: 10 },
    { gain_pct: 100, sell_pct: 15 }, { gain_pct: 250, sell_pct: 10 },
    { gain_pct: 500, sell_pct: 10 }, { gain_pct: 1000, sell_pct: 5 },
    { gain_pct: 2000, sell_pct: 10 },
  ],
  base_trail_drop_pct: 15,
  min_trail_drop_pct: 4,
  decay_after_s: 300,
};

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
  const bots = useFleetLive();
  const control = useBotControl();
  const [logsFor, setLogsFor] = React.useState<string | null>(null);
  const [tuneBot, setTuneBot] = React.useState<BotStatus | null>(null);

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
              {bots.bots?.[0]?.config.usd_per_trade ?? 50} per trade), real controls
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={bots.live ? "default" : "secondary"} className="gap-1.5">
              {bots.live && (
                <span className="relative flex size-2">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />
                  <span className="relative inline-flex size-2 rounded-full bg-current" />
                </span>
              )}
              {bots.live ? "live socket" : "polling"}
            </Badge>
            {bots.bots && (
              <Badge variant="outline" className="font-mono">
                {bots.bots.filter((b) => b.state === "running").length}/{bots.bots.length}{" "}
                running
              </Badge>
            )}
          </div>
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
          <WidgetError error={bots.error} onRetry={() => bots.refetch()} />
        )}
        {bots.bots && (
          <div className="grid gap-3 lg:grid-cols-3">
            {bots.bots.map((bot) => (
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
                    variant="outline"
                    className="h-8"
                    title="Tune parameters"
                    onClick={() => setTuneBot(bot)}
                  >
                    <SlidersHorizontal className="size-3.5" />
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
      <BotConfigSheet bot={tuneBot} onClose={() => setTuneBot(null)} />
    </Card>
  );
}

const FIELDS: {
  key: keyof BotStatus["config"];
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  { key: "usd_per_trade", label: "Position size", min: 1, max: 200, step: 1, unit: "$" },
  { key: "min_confidence", label: "Execution threshold", min: 0, max: 100, step: 1, unit: "/100" },
  { key: "max_open_positions", label: "Max positions", min: 1, max: 10, step: 1, unit: "" },
  { key: "take_profit_pct", label: "Take profit", min: 1, max: 100, step: 1, unit: "%" },
  { key: "stop_loss_pct", label: "Stop loss", min: 1, max: 50, step: 1, unit: "%" },
  { key: "trail_after_pct", label: "Trail after", min: 1, max: 100, step: 1, unit: "%" },
  { key: "trail_drop_pct", label: "Trail drop", min: 1, max: 50, step: 1, unit: "%" },
  { key: "break_even_at_pct", label: "Break-even at", min: 1, max: 100, step: 1, unit: "%" },
  { key: "stall_exit_s", label: "Stall exit", min: 15, max: 600, step: 15, unit: "s" },
  { key: "exit_slippage_bps", label: "Exit slippage", min: 0, max: 1000, step: 5, unit: "bps" },
  { key: "reentry_cooldown_s", label: "Re-entry cooldown", min: 0, max: 3600, step: 30, unit: "s" },
];

function BotConfigSheet({ bot, onClose }: { bot: BotStatus | null; onClose: () => void }) {
  return (
    <Dialog open={bot !== null} onOpenChange={(open) => !open && onClose()}>
      {/* Fixed max-height with a flex column: header/footer stay put, only
          the body between them scrolls. Responsive: 95% on mobile, capped
          at ~640px on desktop. p-0 so header/footer own their own padding. */}
      <DialogContent className="flex max-h-[90vh] w-[95vw] max-w-[640px] flex-col gap-0 overflow-hidden p-0">
        {/* keyed remount seeds fresh initial state per bot — no effect needed */}
        {bot && <BotConfigForm key={bot.config.id} bot={bot} onClose={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

function BotConfigForm({ bot, onClose }: { bot: BotStatus; onClose: () => void }) {
  const update = useUpdateBotConfig();
  const initial = React.useMemo(
    () => Object.fromEntries(FIELDS.map((f) => [f.key, Number(bot.config[f.key] ?? f.min)])),
    [bot],
  );
  const initialPc = React.useMemo<ProfitCapture>(
    () => bot.config.profit_capture ?? DEFAULT_PROFIT_CAPTURE,
    [bot],
  );
  const [values, setValues] = React.useState<Record<string, number>>(initial);
  const [oneShot, setOneShot] = React.useState<boolean>(bot.config.one_shot_per_mint);
  const [pc, setPc] = React.useState<ProfitCapture>(initialPc);

  // The payload of only-changed fields; also powers the dirty check so Save
  // is disabled until something actually differs from the saved config.
  const payload = React.useMemo(() => {
    const p: Record<string, number | boolean | ProfitCapture> = {};
    for (const f of FIELDS) {
      if (values[f.key] !== initial[f.key]) p[f.key] = values[f.key];
    }
    if (oneShot !== bot.config.one_shot_per_mint) p.one_shot_per_mint = oneShot;
    if (JSON.stringify(pc) !== JSON.stringify(initialPc)) p.profit_capture = pc;
    return p;
  }, [values, oneShot, pc, initial, initialPc, bot]);
  const dirty = Object.keys(payload).length > 0;

  function save() {
    if (!dirty) return;
    update.mutate(
      { botId: bot.config.id, update: payload },
      {
        onSuccess: () => {
          toast.success(`${bot.config.name} updated`);
          onClose();
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Update failed"),
      },
    );
  }

  function cancel() {
    // Revert any unsaved changes, then close.
    setValues(initial);
    setOneShot(bot.config.one_shot_per_mint);
    setPc(initialPc);
    onClose();
  }

  return (
    <>
      {/* Fixed header */}
      <DialogHeader className="border-b px-6 py-4">
        <DialogTitle>Tune · {bot.config.name}</DialogTitle>
        <DialogDescription>
          Paper-mode parameters. Changes apply live and persist across restarts.
        </DialogDescription>
      </DialogHeader>

      {/* Scrollable body — the only part that scrolls when content overflows */}
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
        {FIELDS.map((f) => (
          <div key={f.key} className="space-y-2">
            <div className="flex items-baseline justify-between text-sm">
              <label htmlFor={`tune-${f.key}`} className="font-medium">
                {f.label}
              </label>
              <span className="font-mono text-primary tabular-nums">
                {f.unit === "$" && "$"}
                {values[f.key]}
                {f.unit !== "$" && f.unit ? ` ${f.unit}` : ""}
              </span>
            </div>
            <input
              id={`tune-${f.key}`}
              type="range"
              min={f.min}
              max={f.max}
              step={f.step}
              value={values[f.key]}
              onChange={(e) =>
                setValues((v) => ({ ...v, [f.key]: Number(e.target.value) }))
              }
              className="block w-full accent-primary"
            />
          </div>
        ))}

        {/* Dynamic Profit Capture — tiered scale-out replaces fixed TP */}
        <div className="space-y-3 rounded-lg border p-3">
          <button
            type="button"
            onClick={() => setPc((p) => ({ ...p, enabled: !p.enabled }))}
            className="flex w-full items-center justify-between gap-3 text-left text-sm"
          >
            <span>
              <span className="font-medium">Profit Capture</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                sell slices at each profit tier, trail the rest — replaces the
                fixed take-profit while enabled
              </span>
            </span>
            <span
              role="switch"
              aria-checked={pc.enabled}
              className={cn(
                "relative h-6 w-11 shrink-0 rounded-full transition-colors",
                pc.enabled ? "bg-primary" : "bg-muted",
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 size-5 rounded-full bg-white transition-transform",
                  pc.enabled ? "translate-x-[22px]" : "translate-x-0.5",
                )}
              />
            </span>
          </button>

          {pc.enabled && (
            <>
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground">
                  Profit tiers — at each gain, sell this % of the original position
                </p>
                {pc.tiers.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="w-6 text-muted-foreground">+</span>
                    <Input
                      type="number"
                      min={1}
                      max={2000}
                      value={t.gain_pct}
                      onChange={(e) =>
                        setPc((p) => ({
                          ...p,
                          tiers: p.tiers.map((x, j) =>
                            j === i
                              ? { ...x, gain_pct: Math.min(2000, Math.max(1, Number(e.target.value) || 1)) }
                              : x,
                          ),
                        }))
                      }
                      className="h-8 w-20 font-mono"
                    />
                    <span className="text-muted-foreground">% gain → sell</span>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      value={t.sell_pct}
                      onChange={(e) =>
                        setPc((p) => ({
                          ...p,
                          tiers: p.tiers.map((x, j) =>
                            j === i
                              ? { ...x, sell_pct: Math.min(100, Math.max(1, Number(e.target.value) || 1)) }
                              : x,
                          ),
                        }))
                      }
                      className="h-8 w-16 font-mono"
                    />
                    <span className="text-muted-foreground">%</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="ml-auto h-7 px-2 text-muted-foreground"
                      aria-label={`Remove tier ${t.gain_pct}%`}
                      onClick={() =>
                        setPc((p) => ({ ...p, tiers: p.tiers.filter((_, j) => j !== i) }))
                      }
                    >
                      ✕
                    </Button>
                  </div>
                ))}
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={() =>
                    setPc((p) => {
                      const last = p.tiers[p.tiers.length - 1];
                      const gain = Math.min(2000, last ? last.gain_pct * 2 : 5);
                      return { ...p, tiers: [...p.tiers, { gain_pct: gain, sell_pct: 10 }] };
                    })
                  }
                >
                  + Add tier
                </Button>
                {pc.tiers.reduce((s, t) => s + t.sell_pct, 0) > 100 && (
                  <p className="text-xs text-amber-400">
                    Tiers sell more than 100% — later tiers will close whatever remains.
                  </p>
                )}
              </div>

              <div className="grid grid-cols-3 gap-2">
                {(
                  [
                    ["base_trail_drop_pct", "Trail start %", "give-back allowed after the first tier"],
                    ["min_trail_drop_pct", "Trail min %", "tightest give-back on big runners"],
                    ["decay_after_s", "Decay after s", "tighten further when no new tier by then"],
                  ] as const
                ).map(([key, label, hint]) => (
                  <div key={key} title={hint}>
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-muted-foreground">
                      {label}
                    </p>
                    <Input
                      type="number"
                      min={1}
                      value={pc[key]}
                      onChange={(e) =>
                        setPc((p) => ({ ...p, [key]: Math.max(1, Number(e.target.value) || 1) }))
                      }
                      className="h-8 font-mono"
                    />
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Max hold time uses this bot&apos;s existing max-hold setting. Stop-loss,
                stall exit, and rug protections still close positions immediately.
              </p>
            </>
          )}
        </div>

        {/* one trade per coin — the anti-repeat-loss control */}
        <button
          type="button"
          onClick={() => setOneShot((s) => !s)}
          className="flex w-full items-center justify-between gap-3 rounded-lg border p-3 text-left text-sm"
        >
          <span>
            <span className="font-medium">One trade per coin</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              never re-enter a coin — avoids repeat losses on one launch
            </span>
          </span>
          <span
            role="switch"
            aria-checked={oneShot}
            className={cn(
              "relative h-6 w-11 shrink-0 rounded-full transition-colors",
              oneShot ? "bg-primary" : "bg-muted",
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 size-5 rounded-full bg-white transition-transform",
                oneShot ? "translate-x-[22px]" : "translate-x-0.5",
              )}
            />
          </span>
        </button>
      </div>

      {/* Fixed footer */}
      <DialogFooter className="border-t px-6 py-4">
        <Button
          variant="outline"
          className="h-[44px] min-w-[110px] rounded-lg"
          disabled={update.isPending}
          onClick={cancel}
        >
          Cancel
        </Button>
        <Button
          className="h-[44px] w-[150px] rounded-lg"
          disabled={!dirty || update.isPending}
          onClick={save}
        >
          {update.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Saving…
            </>
          ) : (
            "Save Changes"
          )}
        </Button>
      </DialogFooter>
    </>
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
