"use client";

/** Product mark used in the sidebar header and mobile drawer. */
import { Sparkles } from "lucide-react";

import { site } from "@/config/site";
import { cn } from "@/lib/utils";

export function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-1">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary glow-primary">
        <Sparkles className="size-4.5" />
      </div>
      {!collapsed && (
        <div className={cn("flex flex-col leading-tight")}>
          <span className="text-sm font-semibold tracking-tight">
            {site.name}
          </span>
          <span className="text-[11px] text-muted-foreground">
            Operating System
          </span>
        </div>
      )}
    </div>
  );
}
