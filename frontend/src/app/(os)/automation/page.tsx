import { Workflow } from "lucide-react";

import { AgentGrid } from "@/components/agents/agent-grid";
import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/terminal-ui/page-header";
import { BotFleetCard } from "@/components/trading/bot-fleet-card";

export const metadata = { title: "Automation" };

export default function AutomationPage() {
  return (
    <section className="space-y-4">
      <PageHeader
        title="Automation"
        description="The trading bot fleet and the 7-agent pipeline"
        icon={Workflow}
      />
      <FadeIn><BotFleetCard /></FadeIn>
      <FadeIn delay={0.05}><AgentGrid /></FadeIn>
    </section>
  );
}
