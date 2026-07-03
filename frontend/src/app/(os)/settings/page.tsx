import { Settings } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <PagePlaceholder
      title="Settings"
      description="Configuration and preferences"
      icon={Settings}
    />
  );
}
