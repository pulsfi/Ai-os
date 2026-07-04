"use client";

/**
 * AI Chat — streams replies from POST /chat (SSE) token by token.
 *
 * Honest states:
 *  - /chat/status says not configured → banner explaining ANTHROPIC_API_KEY,
 *    composer disabled. No fake responses, ever.
 *  - Mid-stream failure → the partial text stays, an error toast explains.
 */
import * as React from "react";
import { Bot, Loader2, Send, Square, User } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useChatStatus } from "@/hooks/use-backend";
import { ApiError } from "@/lib/api/client";
import { streamChat, type ChatTurn } from "@/lib/api/chat-stream";
import { cn } from "@/lib/utils";

interface DisplayMessage extends ChatTurn {
  id: number;
  streaming?: boolean;
}

export function ChatPanel() {
  const status = useChatStatus();
  const [messages, setMessages] = React.useState<DisplayMessage[]>([]);
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const abortRef = React.useRef<AbortController | null>(null);
  const nextId = React.useRef(1);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  // Keep the newest message in view as tokens stream in.
  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const configured = status.data?.configured ?? false;

  async function send() {
    const text = input.trim();
    if (!text || busy || !configured) return;

    const userMsg: DisplayMessage = { id: nextId.current++, role: "user", content: text };
    const draftId = nextId.current++;
    const history = [...messages, userMsg];

    setMessages([...history, { id: draftId, role: "assistant", content: "", streaming: true }]);
    setInput("");
    setBusy(true);
    abortRef.current = new AbortController();

    try {
      await streamChat(
        history.map(({ role, content }) => ({ role, content })),
        {
          onDelta: (delta) =>
            setMessages((prev) =>
              prev.map((m) =>
                m.id === draftId ? { ...m, content: m.content + delta } : m,
              ),
            ),
        },
        abortRef.current.signal,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // user hit stop — keep whatever streamed in
      } else {
        const message =
          err instanceof ApiError ? err.message : "Chat failed unexpectedly.";
        toast.error(message);
        // Remove an empty draft; keep partial text if some streamed in.
        setMessages((prev) =>
          prev.filter((m) => !(m.id === draftId && m.content === "")),
        );
      }
    } finally {
      setMessages((prev) =>
        prev.map((m) => (m.id === draftId ? { ...m, streaming: false } : m)),
      );
      setBusy(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  return (
    <div className="flex h-[calc(100dvh-10.5rem)] flex-col rounded-xl border bg-card">
      {/* status strip */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Bot className="size-4 text-primary" />
          {status.isLoading ? (
            <Skeleton className="h-4 w-40" />
          ) : configured ? (
            <span>
              Assistant online · <span className="font-mono">{status.data?.model}</span>
            </span>
          ) : (
            <span>Assistant not configured</span>
          )}
        </div>
        <Badge variant={configured ? "default" : "secondary"}>
          {status.isLoading ? "…" : configured ? "ready" : "offline"}
        </Badge>
      </div>

      {/* not-configured banner (honest state, no mock replies) */}
      {!status.isLoading && !configured && (
        <div className="border-b bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
          Add <code className="rounded bg-muted px-1 font-mono">ANTHROPIC_API_KEY</code> to{" "}
          <code className="rounded bg-muted px-1 font-mono">backend/.env</code> and restart
          the backend to enable chat. This UI never fakes responses.
        </div>
      )}

      {/* transcript */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {configured
              ? "Ask about the system, the vault, the market pipeline…"
              : "Chat will activate once the backend has an API key."}
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}
          >
            <div
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-lg",
                m.role === "user"
                  ? "bg-secondary text-secondary-foreground"
                  : "bg-primary/15 text-primary",
              )}
            >
              {m.role === "user" ? <User className="size-4" /> : <Bot className="size-4" />}
            </div>
            <div
              className={cn(
                "max-w-[80%] whitespace-pre-wrap rounded-xl px-4 py-2.5 text-sm leading-relaxed",
                m.role === "user" ? "bg-secondary" : "bg-muted/60",
              )}
            >
              {m.content}
              {m.streaming && (
                <Loader2 className="ml-1 inline size-3.5 animate-spin text-primary" />
              )}
            </div>
          </div>
        ))}
      </div>

      {/* composer */}
      <form
        className="flex items-end gap-2 border-t p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder={configured ? "Message the AI OS… (Enter to send)" : "Chat is offline"}
          disabled={!configured || busy}
          rows={2}
          className="flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        />
        {busy ? (
          <Button type="button" size="icon" variant="secondary" onClick={stop} title="Stop">
            <Square className="size-4" />
          </Button>
        ) : (
          <Button type="submit" size="icon" disabled={!configured || !input.trim()} title="Send">
            <Send className="size-4" />
          </Button>
        )}
      </form>
    </div>
  );
}
