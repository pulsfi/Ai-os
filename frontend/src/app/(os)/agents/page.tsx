import { Bot } from "lucide-react";

import { AgentGrid } from "@/components/agents/agent-grid";

export const metadata = { title: "Agents" };

/**
 * Agent Manager — the 7-agent pipeline read live from the vault via
 * /api/v1/agents. Controls exist but the backend declines them honestly
 * until the Stage 6 runtime opens.
 */
export default function AgentsPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <Bot className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Agent Manager</h2>
          <p className="text-sm text-muted-foreground">
            Pipeline status, reports, and controls — live from the vault
          </p>
        </div>
      </div>
      <AgentGrid />
    </section>
  );
}
