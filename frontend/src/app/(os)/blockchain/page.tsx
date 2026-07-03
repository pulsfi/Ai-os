import { Boxes } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "Blockchain" };

export default function BlockchainPage() {
  return (
    <PagePlaceholder
      title="Blockchain"
      description="Live Solana chain data"
      icon={Boxes}
    />
  );
}
