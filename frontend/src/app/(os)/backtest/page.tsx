import { History } from "lucide-react";

import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/terminal-ui/page-header";
import {
  CoverageCard,
  RankingCard,
  WalkForwardCard,
} from "@/components/backtesting/backtest-panel";

export const metadata = { title: "Backtesting" };

export default function BacktestPage() {
  return (
    <section className="space-y-4">
      <PageHeader
        title="Backtesting"
        description="Capture-replay: strategies validated on recorded reality before they earn live paper trading"
        icon={History}
      />
      <FadeIn><CoverageCard /></FadeIn>
      <FadeIn delay={0.05}><RankingCard /></FadeIn>
      <div className="grid gap-4 lg:grid-cols-2">
        <FadeIn delay={0.1}><WalkForwardCard exitMode="capture" /></FadeIn>
        <FadeIn delay={0.15}><WalkForwardCard exitMode="fixed" /></FadeIn>
      </div>
    </section>
  );
}
