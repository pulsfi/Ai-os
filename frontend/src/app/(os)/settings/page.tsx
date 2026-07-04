import { Settings } from "lucide-react";

import { SettingsPanel } from "@/components/settings/settings-panel";

export const metadata = { title: "Settings" };

/** Live configuration state — backend identity, assistant, providers. */
export default function SettingsPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <Settings className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Settings</h2>
          <p className="text-sm text-muted-foreground">
            Configuration and preferences — secrets stay in backend/.env
          </p>
        </div>
      </div>
      <SettingsPanel />
    </section>
  );
}
