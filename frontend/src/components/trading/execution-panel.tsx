"use client";

/**
 * Execution control (Stage 5) — the live-trading gate, shown honestly.
 *
 * The system ships DISARMED with no real-money path. This panel makes
 * that state legible: current mode, hard risk limits, the go-live
 * readiness scorecard, and a global kill switch (which can only halt).
 * There is deliberately no "go live" button — arming is an operator-only
 * env change, made once the scorecard is fully green.
 */
import {
  CheckCircle2,
  CircleDashed,
  Lock,
  OctagonX,
  ShieldCheck,
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
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import {
  useExecutionStatus,
  useGoLiveReadiness,
  useKillSwitch,
  useSetTradingMode,
} from "@/hooks/use-backend";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function ExecutionPanel() {
  const status = useExecutionStatus();
  const readiness = useGoLiveReadiness();
  const kill = useKillSwitch();
  const setMode = useSetTradingMode();

  function switchMode(mode: "paper" | "live") {
    setMode.mutate(mode, {
      onSuccess: (s) =>
        s.armed
          ? toast.warning("Switched to LIVE — armed. Bots still need a signing wallet; manual trades stay human-approved.")
          : toast.success("Switched to PAPER — safe simulation mode."),
      onError: (err) =>
        toast.error(
          err instanceof ApiError ? err.message : "Could not switch mode",
          { duration: 9000 },
        ),
    });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4 text-primary" /> Live execution
            </CardTitle>
            <CardDescription>
              Stage 5 gate — ships disarmed, no wallet, no signing. Real money
              stays off until the scorecard is green and you arm it deliberately.
            </CardDescription>
          </div>
          {status.data && (
            <Badge
              variant={status.data.armed ? "default" : "secondary"}
              className="gap-1"
            >
              <Lock className="size-3" />
              {status.data.kill_switch
                ? "halted"
                : status.data.armed
                  ? "armed · dry-run"
                  : "disarmed"}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {status.isLoading && <Skeleton className="h-24 rounded-lg" />}
        {status.isError && (
          <WidgetError error={status.error} onRetry={() => void status.refetch()} />
        )}

        {status.data && (
          <>
            {/* PAPER ⇄ LIVE switch — live is gated by the scorecard */}
            <div className="flex items-center gap-3 rounded-lg border p-3">
              <div
                className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1"
                role="group"
                aria-label="Trading mode"
              >
                <button
                  type="button"
                  disabled={setMode.isPending}
                  onClick={() => switchMode("paper")}
                  className={cn(
                    "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
                    !status.data.armed
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-background/60",
                  )}
                >
                  Paper
                </button>
                <button
                  type="button"
                  disabled={setMode.isPending}
                  onClick={() => switchMode("live")}
                  className={cn(
                    "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
                    status.data.armed
                      ? "bg-destructive text-white"
                      : "text-muted-foreground hover:bg-background/60",
                  )}
                >
                  Live
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                {status.data.armed
                  ? "LIVE armed. No autonomous real-money path exists yet — bots stay paper; real trades are wallet-approved."
                  : "PAPER mode. Switching to Live is locked until the readiness scorecard is green."}
              </p>
            </div>

            <div className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
              {status.data.reason}
            </div>

            {/* hard risk limits */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Limit label="Max / order" value={`$${status.data.limits.max_position_usd}`} />
              <Limit
                label="Daily loss halt"
                value={`$${status.data.limits.daily_loss_limit_usd}`}
              />
              <Limit
                label="Max positions"
                value={String(status.data.limits.max_concurrent_positions)}
              />
              <Limit
                label="Max slippage"
                value={`${(status.data.limits.max_slippage_bps / 100).toFixed(1)}%`}
              />
            </div>

            {/* kill switch — only ever halts */}
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center gap-2 text-sm">
                <OctagonX
                  className={cn(
                    "size-4",
                    status.data.kill_switch ? "text-destructive" : "text-muted-foreground",
                  )}
                />
                <span>
                  Global kill switch — {status.data.kill_switch ? "engaged" : "released"}
                </span>
              </div>
              <Button
                size="sm"
                variant={status.data.kill_switch ? "outline" : "destructive"}
                disabled={kill.isPending}
                onClick={() =>
                  kill.mutate(!status.data!.kill_switch, {
                    onSuccess: (s) =>
                      toast[s.kill_switch ? "warning" : "success"](
                        s.kill_switch ? "Execution halted" : "Kill switch released",
                      ),
                    onError: () => toast.error("Kill switch toggle failed"),
                  })
                }
              >
                {status.data.kill_switch ? "Release" : "Halt all"}
              </Button>
            </div>
          </>
        )}

        {/* go-live readiness scorecard */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium">Go-live readiness</h4>
            {readiness.data && (
              <Badge variant={readiness.data.ready ? "default" : "secondary"}>
                {readiness.data.ready ? "READY" : "not ready"}
              </Badge>
            )}
          </div>
          {readiness.isLoading && <Skeleton className="h-24 rounded-lg" />}
          {readiness.data && (
            <>
              <div className="space-y-1.5">
                {readiness.data.criteria.map((c) => (
                  <div
                    key={c.name}
                    className="flex items-center justify-between gap-2 rounded-lg border p-2.5 text-xs"
                  >
                    <div className="flex items-center gap-2">
                      {c.passed ? (
                        <CheckCircle2 className="size-4 text-emerald-400" />
                      ) : (
                        <CircleDashed className="size-4 text-muted-foreground" />
                      )}
                      <span className="font-medium">{c.name}</span>
                    </div>
                    <div className="flex items-center gap-2 font-mono text-muted-foreground">
                      <span className={cn(c.passed && "text-emerald-400")}>{c.actual}</span>
                      <span className="opacity-50">/ {c.target}</span>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{readiness.data.summary}</p>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Limit({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-2.5">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="font-mono text-sm">{value}</p>
    </div>
  );
}
