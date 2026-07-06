import { LineChart } from "lucide-react";

import { WatchlistCard } from "@/components/dashboard/watchlist-card";
import { FadeIn } from "@/components/motion/fade-in";
import { ExecutionLog } from "@/components/terminal-ui/execution-log";
import { TickerBar } from "@/components/terminal-ui/ticker-bar";
import { BotFleetCard } from "@/components/trading/bot-fleet-card";
import { ExecutionPanel } from "@/components/trading/execution-panel";
import { PerformanceCard } from "@/components/trading/performance-card";
import { PumpFunCard } from "@/components/trading/pumpfun-card";
import { TokenInspector } from "@/components/trading/token-inspector";
import { WalletTradePanel } from "@/components/trading/wallet-trade-panel";
import { TrendingCard } from "@/components/trading/trending-card";

export const metadata = { title: "Trading" };

/**
 * Trading terminal — every trade from every bot in one place, live.
 * Read-only market + paper execution: no buy/sell controls until the
 * roadmap's Stage 5 gate opens.
 */
export default function TradingPage() {
  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <LineChart className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Trading Terminal</h2>
          <p className="text-sm text-muted-foreground">
            The fleet&apos;s full record, live — paper mode until the live gate opens
          </p>
        </div>
      </div>

      <FadeIn>
        <TickerBar />
      </FadeIn>

      {/* Live-trading controls first — mode switch + wallet, then the record */}
      <div className="grid gap-4 lg:grid-cols-2">
        <FadeIn delay={0.02} className="lg:col-span-2">
          <ExecutionPanel />
        </FadeIn>
        <FadeIn delay={0.04} className="lg:col-span-2">
          <WalletTradePanel />
        </FadeIn>
      </div>

      <FadeIn delay={0.06}>
        <ExecutionLog />
      </FadeIn>

      <div className="grid gap-4 lg:grid-cols-2">
        <FadeIn delay={0.08} className="lg:col-span-2">
          <BotFleetCard />
        </FadeIn>
        <FadeIn delay={0.1} className="lg:col-span-2">
          <PerformanceCard />
        </FadeIn>
        <FadeIn delay={0.12}>
          <PumpFunCard />
        </FadeIn>
        <FadeIn delay={0.15}>
          <TrendingCard />
        </FadeIn>
        <FadeIn delay={0.18} className="lg:col-span-2">
          <WatchlistCard />
        </FadeIn>
        <FadeIn delay={0.21} className="lg:col-span-2">
          <TokenInspector />
        </FadeIn>
      </div>
    </section>
  );
}
