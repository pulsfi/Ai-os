"use client";

/**
 * Memory — what the system has learned, read from the only live source
 * that exists today: the agents' Reports (via /agents/{name}/reports).
 *
 * The vault's dedicated memory notes (10 Memory/, Training Log) are not
 * exposed by the backend yet — that requires the /vault endpoints
 * (TODO(api) in backend/api/router.py). This page says so honestly
 * instead of inventing content.
 */
import { BrainCircuit, FileText } from "lucide-react";

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
import { useAgents } from "@/hooks/use-backend";

export function MemoryOverview() {
  const agents = useAgents();

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Knowledge held per agent</CardTitle>
          <CardDescription>
            Report output per pipeline agent — the system&apos;s working memory today
          </CardDescription>
        </CardHeader>
        <CardContent>
          {agents.isLoading && <Skeleton className="h-40 rounded-lg" />}
          {agents.isError && (
            <WidgetError error={agents.error} onRetry={() => void agents.refetch()} />
          )}
          {agents.data && (
            <div className="space-y-2">
              {agents.data.map((a) => (
                <div
                  key={a.name}
                  className="flex items-center justify-between gap-3 rounded-lg border p-3"
                >
                  <div className="flex items-center gap-2">
                    <BrainCircuit className="size-4 text-primary" />
                    <span className="text-sm">{a.name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <FileText className="size-3.5" />
                    <span>
                      {a.report_count} report{a.report_count === 1 ? "" : "s"}
                    </span>
                    {a.last_report_date && (
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {a.last_report_date}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Vault memory notes</CardTitle>
          <CardDescription>Training Log, lessons, and long-term memory</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            The vault&apos;s memory notes (<span className="font-mono">10 Memory/</span>,
            Training Log) are not exposed by the backend yet — the{" "}
            <span className="font-mono">/vault</span> endpoints are the next backend
            milestone. Until then, open them directly in Obsidian. No placeholder
            data is shown here by design.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
