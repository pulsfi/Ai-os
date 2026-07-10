import { Radar } from "lucide-react";

import { WatchlistCard } from "@/components/dashboard/watchlist-card";
import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/terminal-ui/page-header";
import { PumpFunCard } from "@/components/trading/pumpfun-card";
import { TrendingCard } from "@/components/trading/trending-card";

export const metadata = { title: "Live Scanner" };

export default function ScannerPage() {
  return (
    <section className="space-y-4">
      <PageHeader title="Live Scanner" description="New pump.fun launches and market movers, live" icon={Radar} />
      <FadeIn><PumpFunCard /></FadeIn>
      <div className="grid gap-4 lg:grid-cols-2">
        <FadeIn delay={0.05}><TrendingCard /></FadeIn>
        <FadeIn delay={0.1}><WatchlistCard /></FadeIn>
      </div>
    </section>
  );
}
