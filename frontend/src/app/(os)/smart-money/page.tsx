import { Waypoints } from "lucide-react";

import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/terminal-ui/page-header";
import { TokenInspector } from "@/components/trading/token-inspector";

export const metadata = { title: "Smart Money" };

export default function SmartMoneyPage() {
  return (
    <section className="space-y-4">
      <PageHeader
        title="Smart Money"
        description="Live buy/sell flow and wallet activity for any token (Helius)"
        icon={Waypoints}
      />
      <FadeIn><TokenInspector /></FadeIn>
    </section>
  );
}
