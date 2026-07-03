import { Bot } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "Agents" };

export default function AgentsPage() {
  return (
    <PagePlaceholder
      title="Agents"
      description="The seven-agent roster and their status"
      icon={Bot}
    />
  );
}
