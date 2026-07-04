import { LineChart } from "lucide-react";

import { WatchlistCard } from "@/components/dashboard/watchlist-card";
import { FadeIn } from "@/components/motion/fade-in";
import { TokenInspector } from "@/components/trading/token-inspector";
import { TrendingCard } from "@/components/trading/trending-card";

export const metadata = { title: "Trading" };

/**
 * Trading — live market intelligence (read-only). Execution stays in the
 * paper-trading layer until the roadmap's Stage 5 gate opens; this page
 * deliberately has no buy/sell controls.
 */
export default function TradingPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <LineChart className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Trading</h2>
          <p className="text-sm text-muted-foreground">
            Live market intelligence — read-only until the live-execution gate opens
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <FadeIn className="lg:col-span-2">
          <WatchlistCard />
        </FadeIn>
        <FadeIn delay={0.05}>
          <TrendingCard />
        </FadeIn>
        <FadeIn delay={0.1}>
          <TokenInspector />
        </FadeIn>
      </div>
    </section>
  );
}
