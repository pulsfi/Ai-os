"use client";

/**
 * Vault notes browser — real markdown from the Obsidian vault via the
 * read-only /vault endpoints (allowlisted folders only).
 */
import * as React from "react";
import { FileText, FolderOpen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useVaultDirs, useVaultNote, useVaultNotes } from "@/hooks/use-backend";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

export function VaultNotesCard() {
  const dirs = useVaultDirs();
  const [dir, setDir] = React.useState("10 Memory");
  const notes = useVaultNotes(dir);
  const [selectedPath, setSelectedPath] = React.useState("");

  // Derived, not effect-driven: fall back to the freshest note whenever the
  // explicit selection isn't part of the current folder's listing.
  const effectivePath =
    notes.data?.some((n) => n.path === selectedPath) === true
      ? selectedPath
      : (notes.data?.[0]?.path ?? "");
  const note = useVaultNote(effectivePath);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FolderOpen className="size-4 text-primary" /> Vault notes
        </CardTitle>
        <CardDescription>
          Read live from the Obsidian vault (read-only bridge)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* folder tabs */}
        <div className="flex flex-wrap gap-1.5">
          {dirs.isLoading && <Skeleton className="h-7 w-48 rounded-full" />}
          {dirs.data?.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDir(d)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                d === dir
                  ? "border-primary bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {d}
            </button>
          ))}
        </div>

        {notes.isError && (
          <WidgetError error={notes.error} onRetry={() => void notes.refetch()} />
        )}

        <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
          {/* note list */}
          <div className="space-y-1.5">
            {notes.isLoading && <Skeleton className="h-24 rounded-lg" />}
            {notes.data?.length === 0 && (
              <p className="text-xs text-muted-foreground">No notes in this folder.</p>
            )}
            {notes.data?.map((n) => (
              <button
                key={n.path}
                type="button"
                onClick={() => setSelectedPath(n.path)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg border p-2.5 text-left text-xs transition-colors",
                  n.path === effectivePath
                    ? "border-primary bg-primary/10"
                    : "hover:bg-muted",
                )}
              >
                <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate">{n.name}</span>
                <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                  {timeAgo(n.modified)}
                </span>
              </button>
            ))}
          </div>

          {/* note content */}
          <div className="min-h-64 rounded-lg border">
            {note.isLoading && <Skeleton className="m-3 h-56 rounded" />}
            {note.isError && (
              <p className="p-4 text-xs text-destructive">Could not load this note.</p>
            )}
            {note.data && (
              <div className="flex h-full flex-col">
                <div className="flex items-center justify-between border-b px-4 py-2">
                  <span className="text-sm font-medium">{note.data.name}</span>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {note.data.path}
                  </Badge>
                </div>
                <ScrollArea className="max-h-96 flex-1">
                  <pre className="whitespace-pre-wrap p-4 font-sans text-xs leading-relaxed text-muted-foreground">
                    {note.data.content}
                  </pre>
                </ScrollArea>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
