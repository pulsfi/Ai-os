import { TerminalSquare } from "lucide-react";

import { ApiConsole } from "@/components/terminal/api-console";

export const metadata = { title: "Terminal" };

/**
 * Terminal — a real read-only API console against the live backend.
 * (Arbitrary shell execution is deliberately not exposed; see the note
 * inside ApiConsole.)
 */
export default function TerminalPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <TerminalSquare className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Terminal</h2>
          <p className="text-sm text-muted-foreground">
            Query any backend endpoint directly — live requests, live responses
          </p>
        </div>
      </div>
      <ApiConsole />
    </section>
  );
}
