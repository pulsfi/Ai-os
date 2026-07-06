"use client";

/**
 * Alerts — recent system events (kill switch, mode change, real trades…).
 * New alerts pop as toasts; everything also fires to Telegram when a bot
 * token is configured. Works with zero config via the in-app feed.
 */
import * as React from "react";
import { Bell, Send, TriangleAlert } from "lucide-react";
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
import { useAlerts, useTestAlert } from "@/hooks/use-backend";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

const LEVEL_DOT: Record<string, string> = {
  info: "bg-sky-400",
  warning: "bg-amber-400",
  critical: "bg-red-400",
};

/** Toast alerts that arrive after mount (never re-toast history on load). */
function useAlertToasts(alerts: ReturnType<typeof useAlerts>) {
  const lastSeen = React.useRef<string | null>(null);
  React.useEffect(() => {
    const list = alerts.data?.alerts ?? [];
    if (list.length === 0) return;
    const newest = list[0].ts;
    if (lastSeen.current === null) {
      lastSeen.current = newest; // first load: adopt, don't toast
      return;
    }
    if (newest > lastSeen.current) {
      for (const a of list) {
        if (a.ts > lastSeen.current) {
          const fn = a.level === "critical" ? toast.error : a.level === "warning" ? toast.warning : toast.info;
          fn(a.title, { description: a.message });
        }
      }
      lastSeen.current = newest;
    }
  }, [alerts.data]);
}

export function AlertsCard() {
  const alerts = useAlerts();
  const test = useTestAlert();
  useAlertToasts(alerts);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Bell className="size-4 text-primary" /> Alerts
            </CardTitle>
            <CardDescription>
              System events — kill switch, mode changes, real trades
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {alerts.data && (
              <Badge variant={alerts.data.telegram_configured ? "default" : "secondary"}>
                <Send className="mr-1 size-3" />
                {alerts.data.telegram_configured ? "Telegram on" : "in-app only"}
              </Badge>
            )}
            <Button
              size="sm"
              variant="outline"
              className="h-8"
              disabled={test.isPending}
              onClick={() =>
                test.mutate(undefined, {
                  onError: () => toast.error("Test failed"),
                })
              }
            >
              Test
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {alerts.isLoading && <Skeleton className="h-24 rounded-lg" />}
        {alerts.isError && (
          <WidgetError error={alerts.error} onRetry={() => void alerts.refetch()} />
        )}
        {alerts.data && alerts.data.alerts.length === 0 && (
          <p className="py-4 text-center text-xs text-muted-foreground">
            No alerts yet. Events will appear here as they happen.
          </p>
        )}
        {alerts.data && alerts.data.alerts.length > 0 && (
          <div className="max-h-72 space-y-1.5 overflow-y-auto">
            {alerts.data.alerts.map((a, i) => (
              <div
                key={`${a.ts}-${i}`}
                className="flex items-start gap-2.5 rounded-lg border p-2.5 text-xs"
              >
                <span
                  className={cn(
                    "mt-1 size-2 shrink-0 rounded-full",
                    LEVEL_DOT[a.level] ?? "bg-muted-foreground",
                  )}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 font-medium">
                      {a.level === "critical" && (
                        <TriangleAlert className="size-3.5 text-red-400" />
                      )}
                      {a.title}
                    </span>
                    <span className="shrink-0 text-[10px] text-muted-foreground">
                      {timeAgo(a.ts)}
                    </span>
                  </div>
                  <p className="text-muted-foreground">{a.message}</p>
                </div>
              </div>
            ))}
          </div>
        )}
        {alerts.data && !alerts.data.telegram_configured && (
          <p className="mt-3 text-[11px] text-muted-foreground">
            Add <code className="font-mono">TELEGRAM_BOT_TOKEN</code> +{" "}
            <code className="font-mono">TELEGRAM_CHAT_ID</code> to backend/.env for
            phone push notifications.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
