import { LayoutDashboard } from "lucide-react";

import { ChainStatusCard } from "@/components/dashboard/chain-status-card";
import { MarketStatusCard } from "@/components/dashboard/market-status-card";
import { SystemHealthCard } from "@/components/dashboard/system-health-card";
import { WatchlistCard } from "@/components/dashboard/watchlist-card";
import { FadeIn } from "@/components/motion/fade-in";

export const metadata = { title: "Dashboard" };

/**
 * System overview — every widget reads live backend data through its own
 * query hook and degrades independently (skeleton → data | inline error).
 */
export default function DashboardPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <LayoutDashboard className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Dashboard</h2>
          <p className="text-sm text-muted-foreground">
            Live system, chain, and market overview
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <FadeIn>
          <SystemHealthCard />
        </FadeIn>
        <FadeIn delay={0.05}>
          <ChainStatusCard />
        </FadeIn>
        <FadeIn delay={0.1} className="lg:col-span-2">
          <WatchlistCard />
        </FadeIn>
        <FadeIn delay={0.15} className="lg:col-span-2">
          <MarketStatusCard />
        </FadeIn>
      </div>
    </section>
  );
}
