import { TerminalSquare } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "Terminal" };

export default function TerminalPage() {
  return (
    <PagePlaceholder
      title="Terminal"
      description="Live logs and command console"
      icon={TerminalSquare}
    />
  );
}
