import { MessagesSquare } from "lucide-react";

import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const metadata = { title: "AI Chat" };

export default function ChatPage() {
  return (
    <PagePlaceholder
      title="AI Chat"
      description="Converse with the AI operating system"
      icon={MessagesSquare}
    />
  );
}
