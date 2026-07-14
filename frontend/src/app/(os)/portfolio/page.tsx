import { Wallet } from "lucide-react";

import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/terminal-ui/page-header";
import { PerformanceCard } from "@/components/trading/performance-card";
import { PaperLedgerCard } from "@/components/trading/paper-ledger-card";
import { RiskCard } from "@/components/trading/risk-card";
import { WalletTradePanel } from "@/components/trading/wallet-trade-panel";

export const metadata = { title: "Portfolio" };

export default function PortfolioPage() {
  return (
    <section className="space-y-4">
      <PageHeader
        title="Portfolio"
        description="Paper track record, positions, risk budgets, and your real wallet trades"
        icon={Wallet}
      />
      <FadeIn><RiskCard /></FadeIn>
      <FadeIn delay={0.05}><WalletTradePanel /></FadeIn>
      <FadeIn delay={0.1}><PerformanceCard /></FadeIn>
      <FadeIn delay={0.15}><PaperLedgerCard /></FadeIn>
    </section>
  );
}
