import { FlaskConical } from "lucide-react";

import { FadeIn } from "@/components/motion/fade-in";
import { PageHeader } from "@/components/terminal-ui/page-header";
import { TokenInspector } from "@/components/trading/token-inspector";
import { VaultNotesCard } from "@/components/memory/vault-notes-card";

export const metadata = { title: "Research" };

export default function ResearchPage() {
  return (
    <section className="space-y-4">
      <PageHeader
        title="Research"
        description="Inspect and score any token; browse the knowledge vault"
        icon={FlaskConical}
      />
      <FadeIn><TokenInspector /></FadeIn>
      <FadeIn delay={0.05}><VaultNotesCard /></FadeIn>
    </section>
  );
}
