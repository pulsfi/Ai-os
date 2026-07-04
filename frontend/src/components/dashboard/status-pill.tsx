/** Colored status pill for ok/degraded/down — the health vocabulary. */
import { cn } from "@/lib/utils";
import type { HealthStatus } from "@/types/api";

const styles: Record<HealthStatus, string> = {
  ok: "bg-success/15 text-success",
  degraded: "bg-warning/15 text-warning",
  down: "bg-destructive/15 text-destructive",
};

export function StatusPill({
  status,
  label,
  className,
}: {
  status: HealthStatus;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium",
        styles[status],
        className,
      )}
    >
      <span className="relative flex size-1.5">
        {status === "ok" && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />
        )}
        <span className="relative inline-flex size-1.5 rounded-full bg-current" />
      </span>
      {label ?? status}
    </span>
  );
}
