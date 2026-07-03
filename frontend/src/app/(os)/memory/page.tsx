import { BrainCircuit } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "Memory" };

export default function MemoryPage() {
  return (
    <PagePlaceholder
      title="Memory"
      description="Long-term system memory and lessons"
      icon={BrainCircuit}
    />
  );
}
