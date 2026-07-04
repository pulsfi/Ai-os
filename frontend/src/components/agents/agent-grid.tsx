"use client";

/**
 * Agent Manager — status cards for the 7-agent vault pipeline, with a
 * detail/log drawer per agent.
 *
 * Controls (start/stop/restart) call the real backend endpoint, which
 * currently DECLINES with a reason (no process runtime until Stage 6).
 * That reason is shown to the user verbatim — nothing is faked.
 */
import * as React from "react";
import {
  Activity,
  Bot,
  FileText,
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
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useAgent, useAgentControl, useAgentReports, useAgents } from "@/hooks/use-backend";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

function statusVariant(status: string): "default" | "secondary" | "outline" {
  if (status === "active") return "default";
  if (status === "standby" || status === "paused") return "secondary";
  return "outline";
}

export function AgentGrid() {
  const agents = useAgents();
  const control = useAgentControl();
  const [selected, setSelected] = React.useState<string | null>(null);

  function act(name: string, action: "start" | "stop" | "restart") {
    control.mutate(
      { name, action },
      {
        onSuccess: (res) => {
          if (res.accepted) {
            toast.success(`${res.agent}: ${res.action} accepted`);
          } else {
            // Honest gate: the backend explains why controls are inert.
            toast.info(res.reason, { duration: 8000 });
          }
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Control request failed"),
      },
    );
  }

  if (agents.isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="h-44 rounded-xl" />
        ))}
      </div>
    );
  }

  if (agents.isError) {
    return <WidgetError error={agents.error} onRetry={() => void agents.refetch()} />;
  }

  return (
    <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {agents.data?.map((agent) => (
          <Card key={agent.name} className="flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "flex size-8 items-center justify-center rounded-lg",
                      agent.status === "active"
                        ? "bg-primary/15 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    <Bot className="size-4" />
                  </div>
                  <CardTitle className="text-base">{agent.name}</CardTitle>
                </div>
                <Badge variant={statusVariant(agent.status)}>{agent.status}</Badge>
              </div>
              <CardDescription className="line-clamp-2 min-h-10">
                {agent.description || "No description in the vault yet."}
              </CardDescription>
            </CardHeader>
            <CardContent className="mt-auto space-y-3">
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <FileText className="size-3.5" />
                  {agent.report_count} report{agent.report_count === 1 ? "" : "s"}
                </span>
                {agent.last_activity && (
                  <span className="inline-flex items-center gap-1">
                    <Activity className="size-3.5" />
                    {timeAgo(agent.last_activity)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  disabled={control.isPending}
                  onClick={() => act(agent.name, "start")}
                >
                  <Play className="size-3.5" /> Start
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  disabled={control.isPending}
                  onClick={() => act(agent.name, "stop")}
                >
                  <Square className="size-3.5" /> Stop
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  disabled={control.isPending}
                  onClick={() => act(agent.name, "restart")}
                >
                  <RotateCcw className="size-3.5" /> Restart
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="ml-auto h-8"
                  onClick={() => setSelected(agent.name)}
                >
                  <ScrollText className="size-3.5" /> Logs
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <AgentDetailSheet name={selected} onClose={() => setSelected(null)} />
    </>
  );
}

function AgentDetailSheet({ name, onClose }: { name: string | null; onClose: () => void }) {
  const detail = useAgent(name ?? "");
  const reports = useAgentReports(name ?? "");

  return (
    <Sheet open={name !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-hidden sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{name}</SheetTitle>
          <SheetDescription>
            Mission, activity, and report log — read live from the vault
          </SheetDescription>
        </SheetHeader>
        <ScrollArea className="h-[calc(100dvh-7rem)] pr-4">
          <div className="space-y-5 px-4 pb-8">
            {detail.isLoading && <Skeleton className="h-24 rounded-lg" />}
            {detail.data && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Mission</h4>
                <pre className="whitespace-pre-wrap rounded-lg bg-muted/50 p-3 font-sans text-xs leading-relaxed text-muted-foreground">
                  {detail.data.mission.trim() || "No Mission.md content."}
                </pre>
              </div>
            )}

            <Separator />

            <div className="space-y-3">
              <h4 className="text-sm font-medium">
                Reports {reports.data ? `(${reports.data.length})` : ""}
              </h4>
              {reports.isLoading && <Skeleton className="h-24 rounded-lg" />}
              {reports.isError && (
                <p className="text-xs text-destructive">Could not load reports.</p>
              )}
              {reports.data?.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No reports yet — this agent has not produced output.
                </p>
              )}
              {reports.data?.map((r) => (
                <div key={`${r.date}-${r.title}`} className="rounded-lg border p-3">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{r.title}</span>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {r.date}
                    </Badge>
                  </div>
                  <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-muted-foreground">
                    {r.body}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
