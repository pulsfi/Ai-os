"use client";

/** Inline error state for one dashboard widget — the rest of the dashboard
 *  keeps working (per-widget degradation, mirroring the backend philosophy). */
import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";

export function WidgetError({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  const message =
    error instanceof ApiError
      ? error.message
      : "Something went wrong loading this data.";

  return (
    <div className="flex min-h-32 flex-col items-center justify-center gap-2 py-4 text-center">
      <AlertTriangle className="size-5 text-destructive" />
      <p className="max-w-xs text-xs text-muted-foreground">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RotateCw className="size-3.5" /> Retry
      </Button>
    </div>
  );
}
