import { Boxes } from "lucide-react";

import { RugCheckCard } from "@/components/blockchain/rug-check-card";
import { ChainStatusCard } from "@/components/dashboard/chain-status-card";
import { FadeIn } from "@/components/motion/fade-in";

export const metadata = { title: "Blockchain" };

/** Live Solana mainnet view: chain status + on-chain token rug check. */
export default function BlockchainPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <Boxes className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Blockchain</h2>
          <p className="text-sm text-muted-foreground">
            Live Solana chain data and on-chain token safety checks
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <FadeIn>
          <ChainStatusCard />
        </FadeIn>
        <FadeIn delay={0.05}>
          <RugCheckCard />
        </FadeIn>
      </div>
    </section>
  );
}
