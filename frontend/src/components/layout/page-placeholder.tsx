/**
 * Milestone-1 placeholder for a not-yet-built feature page. Establishes the
 * route, title, and a consistent "coming next" surface. Feature pages replace
 * these in later milestones — the routing and shell are already real.
 */
import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

interface PagePlaceholderProps {
  title: string;
  description: string;
  icon: LucideIcon;
}

export function PagePlaceholder({
  title,
  description,
  icon: Icon,
}: PagePlaceholderProps) {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <Icon className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>

      <Card className="border-dashed">
        <CardContent className="flex min-h-52 flex-col items-center justify-center gap-2 text-center">
          <Icon className="size-8 text-muted-foreground/50" />
          <p className="text-sm font-medium">Coming next</p>
          <p className="max-w-sm text-xs text-muted-foreground">
            This section is scaffolded. Its live features arrive in a later
            milestone, wired to the FastAPI backend.
          </p>
        </CardContent>
      </Card>
    </section>
  );
}
