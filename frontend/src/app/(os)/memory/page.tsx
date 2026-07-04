import { BrainCircuit } from "lucide-react";

import { MemoryOverview } from "@/components/memory/memory-overview";

export const metadata = { title: "Memory" };

/** What the system has learned — live agent reports; vault notes TBD. */
export default function MemoryPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <BrainCircuit className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Memory</h2>
          <p className="text-sm text-muted-foreground">
            Long-term system memory and lessons
          </p>
        </div>
      </div>
      <MemoryOverview />
    </section>
  );
}
