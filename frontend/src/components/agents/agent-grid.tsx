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
  TriangleAlert,
  Workflow,
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
import {
  useAgent,
  useAgentActivity,
  useAgentControl,
  useAgentReports,
  useAgentRuntime,
  useAgents,
} from "@/hooks/use-backend";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

function RuntimeBadge({ state }: { state: string }) {
  if (state === "running") {
    return (
      <Badge className="gap-1.5">
        <span className="relative flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />
          <span className="relative inline-flex size-2 rounded-full bg-current" />
        </span>
        live
      </Badge>
    );
  }
  if (state === "error") {
    return (
      <Badge variant="destructive" className="gap-1">
        <TriangleAlert className="size-3" /> error
      </Badge>
    );
  }
  if (state === "stopped") return <Badge variant="secondary">stopped</Badge>;
  return <Badge variant="outline">idle</Badge>;
}

export function AgentGrid() {
  const agents = useAgents();
  const runtime = useAgentRuntime();
  const control = useAgentControl();
  const [selected, setSelected] = React.useState<string | null>(null);

  function act(name: string, action: "start" | "stop" | "restart") {
    control.mutate(
      { name, action },
      {
        onSuccess: (res) => {
          const verb = res.accepted ? "success" : "info";
          toast[verb](`${res.agent}: ${res.reason} (${res.runtime_state})`);
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
      {/* live pipeline banner */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-card/60 px-4 py-3">
        <div className="flex items-center gap-2 text-sm">
          <Workflow className="size-4 text-primary" />
          <span className="font-medium">7-agent pipeline</span>
          {runtime.data && (
            <RuntimeBadge state={runtime.data.running ? "running" : "stopped"} />
          )}
        </div>
        {runtime.data && (
          <span className="font-mono text-xs text-muted-foreground">
            {runtime.data.cycles} cycles · every {runtime.data.cycle_seconds}s ·{" "}
            {runtime.data.agents.filter((a) => a.enabled).length}/
            {runtime.data.agents.length} active
          </span>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {agents.data?.map((agent) => (
          <Card key={agent.name} className="flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "flex size-8 items-center justify-center rounded-lg",
                      agent.runtime_state === "running"
                        ? "bg-primary/15 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    <Bot className="size-4" />
                  </div>
                  <CardTitle className="text-base">{agent.name}</CardTitle>
                </div>
                <RuntimeBadge state={agent.runtime_state} />
              </div>
              <CardDescription className="line-clamp-2 min-h-10">
                {agent.description || "No description in the vault yet."}
              </CardDescription>
            </CardHeader>
            <CardContent className="mt-auto space-y-3">
              {/* what the agent is doing right now (live) */}
              <div className="min-h-9 rounded-lg bg-muted/40 px-2.5 py-1.5 text-xs">
                {agent.last_summary ? (
                  <span className={cn(agent.last_ok === false && "text-destructive")}>
                    {agent.last_summary}
                  </span>
                ) : (
                  <span className="text-muted-foreground">Waiting for first cycle…</span>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <Activity className="size-3.5" />
                  {agent.cycles} runs
                </span>
                {agent.last_run && (
                  <span className="inline-flex items-center gap-1">
                    {timeAgo(agent.last_run)}
                  </span>
                )}
                <span className="inline-flex items-center gap-1">
                  <FileText className="size-3.5" />
                  {agent.report_count}
                </span>
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
  const activity = useAgentActivity(name ?? "");

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
            {/* live pipeline activity (Stage 6) */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Live activity</h4>
              {activity.isLoading && <Skeleton className="h-20 rounded-lg" />}
              {activity.data?.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No pipeline output yet — the agent runs on the next cycle.
                </p>
              )}
              <div className="space-y-1.5">
                {activity.data?.map((t, i) => (
                  <div
                    key={`${t.ts}-${i}`}
                    className="rounded-lg border p-2.5 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={cn(!t.ok && "text-destructive")}>{t.summary}</span>
                      <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                        {timeAgo(t.ts)}
                      </span>
                    </div>
                    {t.detail && (
                      <p className="mt-0.5 text-muted-foreground">{t.detail}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Separator />

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
