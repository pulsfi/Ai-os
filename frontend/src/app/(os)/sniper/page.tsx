import { Crosshair } from "lucide-react";

import { FadeIn } from "@/components/motion/fade-in";
import { ExecutionLog } from "@/components/terminal-ui/execution-log";
import { PageHeader } from "@/components/terminal-ui/page-header";
import { BotFleetCard } from "@/components/trading/bot-fleet-card";
import { ExecutionPanel } from "@/components/trading/execution-panel";

export const metadata = { title: "Launch Sniper" };

export default function SniperPage() {
  return (
    <section className="space-y-4">
      <PageHeader
        title="Launch Sniper"
        description="Bots score every launch 0–100 and only enter high-confidence ones — paper mode"
        icon={Crosshair}
      />
      <FadeIn><BotFleetCard /></FadeIn>
      <FadeIn delay={0.05}><ExecutionPanel /></FadeIn>
      <FadeIn delay={0.1}><ExecutionLog /></FadeIn>
    </section>
  );
}
