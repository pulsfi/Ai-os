"use client";

/** A single at-a-glance metric tile for the terminal header rail. */
import type { LucideIcon } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function KpiTile({
  label,
  value,
  sub,
  icon: Icon,
  tone,
  loading,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: LucideIcon;
  tone?: "up" | "down" | "warn" | "accent";
  loading?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col justify-between rounded-lg border bg-card/70 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          {label}
        </span>
        <Icon
          className={cn(
            "size-3.5 shrink-0",
            tone === "up" && "text-emerald-400",
            tone === "down" && "text-red-400",
            tone === "warn" && "text-amber-400",
            (tone === "accent" || !tone) && "text-primary",
          )}
        />
      </div>
      {loading ? (
        <Skeleton className="mt-2 h-6 w-20" />
      ) : (
        <div className="mt-1.5 flex items-baseline gap-1.5">
          <span
            className={cn(
              "truncate font-mono text-lg font-semibold tabular-nums",
              tone === "up" && "text-emerald-400",
              tone === "down" && "text-red-400",
              tone === "warn" && "text-amber-400",
            )}
          >
            {value}
          </span>
        </div>
      )}
      {sub && !loading && (
        <span className="mt-0.5 truncate text-[11px] text-muted-foreground">{sub}</span>
      )}
    </div>
  );
}
