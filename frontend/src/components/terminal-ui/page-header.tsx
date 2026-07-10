import type { LucideIcon } from "lucide-react";

/** Consistent section header used across the terminal pages. */
export function PageHeader({
  title,
  description,
  icon: Icon,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
        <Icon className="size-5" />
      </div>
      <div>
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
