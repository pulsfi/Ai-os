"use client";

/**
 * Memory — what the system has learned: vault memory notes (live via the
 * read-only /vault bridge) + per-agent report activity (/agents).
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
import { VaultNotesCard } from "@/components/memory/vault-notes-card";
import { useAgents } from "@/hooks/use-backend";

export function MemoryOverview() {
  const agents = useAgents();

  return (
    <div className="space-y-4">
      <VaultNotesCard />
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

    </div>
  );
}
