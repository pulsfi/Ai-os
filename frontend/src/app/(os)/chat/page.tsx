import { MessagesSquare } from "lucide-react";

import { ChatPanel } from "@/components/chat/chat-panel";

export const metadata = { title: "AI Chat" };

/** Streaming conversation with the backend's Claude-powered assistant. */
export default function ChatPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary glow-primary">
          <MessagesSquare className="size-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">AI Chat</h2>
          <p className="text-sm text-muted-foreground">
            Converse with the AI operating system — streamed live from the backend
          </p>
        </div>
      </div>
      <ChatPanel />
    </section>
  );
}
