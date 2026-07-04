"use client";

/**
 * API console — a real terminal against the live backend: type any GET
 * endpoint path and see the actual JSON response (or the actual error).
 *
 * This is intentionally NOT a fake shell. A command-execution backend does
 * not exist (and running arbitrary shell commands from the browser would be
 * a security hole); this console only issues read-only GET requests to the
 * FastAPI service.
 */
import * as React from "react";
import { ChevronRight, TerminalSquare } from "lucide-react";

import { http, ApiError } from "@/lib/api/client";
import { apiBaseUrl } from "@/config/env";
import { cn } from "@/lib/utils";

interface ConsoleEntry {
  id: number;
  path: string;
  ok: boolean;
  ms: number;
  body: string;
}

const SUGGESTIONS = [
  "/health",
  "/system/info",
  "/solana/status",
  "/market/tokens",
  "/market/status",
  "/agents",
  "/chat/status",
];

/** Issue the GET and time it — module scope keeps the component pure. */
async function executeGet(path: string): Promise<Omit<ConsoleEntry, "id">> {
  const started = Date.now();
  try {
    const res = await http.get(path);
    return {
      path,
      ok: true,
      ms: Date.now() - started,
      body: JSON.stringify(res.data, null, 2),
    };
  } catch (err) {
    const body =
      err instanceof ApiError
        ? JSON.stringify({ error: { code: err.code, message: err.message } }, null, 2)
        : String(err);
    return { path, ok: false, ms: Date.now() - started, body };
  }
}

export function ApiConsole() {
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [entries, setEntries] = React.useState<ConsoleEntry[]>([]);
  const nextId = React.useRef(1);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [entries]);

  async function run(rawPath: string) {
    const path = rawPath.trim();
    if (!path || busy) return;
    setBusy(true);
    const normalized = path.startsWith("/") ? path : `/${path}`;
    try {
      const entry = await executeGet(normalized);
      setEntries((prev) => [...prev, { id: nextId.current++, ...entry }]);
    } finally {
      setBusy(false);
      setInput("");
    }
  }

  return (
    <div className="flex h-[calc(100dvh-12.5rem)] flex-col overflow-hidden rounded-xl border bg-card font-mono text-xs">
      <div className="flex items-center gap-2 border-b px-4 py-2 text-muted-foreground">
        <TerminalSquare className="size-4 text-primary" />
        <span>
          GET console → <span className="text-foreground">{apiBaseUrl}</span>
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {entries.length === 0 && (
          <div className="space-y-2 text-muted-foreground">
            <p>Read-only console against the live backend. Try:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => void run(s)}
                  className="rounded border px-2 py-1 hover:bg-muted"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {entries.map((e) => (
          <div key={e.id}>
            <div className="flex items-center gap-2">
              <ChevronRight className="size-3.5 text-primary" />
              <span>GET {e.path}</span>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10px]",
                  e.ok ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400",
                )}
              >
                {e.ok ? "ok" : "error"} · {e.ms}ms
              </span>
            </div>
            <pre className="mt-1 max-h-72 overflow-auto whitespace-pre rounded-lg bg-muted/50 p-3 leading-relaxed">
              {e.body}
            </pre>
          </div>
        ))}
      </div>

      <form
        className="flex items-center gap-2 border-t px-4 py-3"
        onSubmit={(event) => {
          event.preventDefault();
          void run(input);
        }}
      >
        <span className="text-primary">GET</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="/market/trending"
          disabled={busy}
          spellCheck={false}
          className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground/60"
        />
      </form>
    </div>
  );
}
