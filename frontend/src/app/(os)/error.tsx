"use client";

/** Route-level error boundary for the (os) group. Every feature page inherits
 *  it, so a thrown render/data error shows a recoverable UI instead of a blank
 *  screen. Client component by requirement (error boundaries are client-only). */
import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function OsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // TODO(observability): forward to a logging service when one is chosen.
    console.error(error);
  }, [error]);

  return (
    <Card className="border-destructive/40">
      <CardContent className="flex min-h-52 flex-col items-center justify-center gap-3 text-center">
        <AlertTriangle className="size-8 text-destructive" />
        <p className="text-sm font-medium">Something went wrong</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          {error.message || "An unexpected error occurred in this section."}
        </p>
        <Button variant="outline" size="sm" onClick={reset}>
          Try again
        </Button>
      </CardContent>
    </Card>
  );
}
