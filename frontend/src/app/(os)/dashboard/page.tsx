import { LayoutDashboard } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <PagePlaceholder
      title="Dashboard"
      description="System overview and live metrics"
      icon={LayoutDashboard}
    />
  );
}
