import { LineChart } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "Trading" };

export default function TradingPage() {
  return (
    <PagePlaceholder
      title="Trading"
      description="Market intelligence and paper trading"
      icon={LineChart}
    />
  );
}
