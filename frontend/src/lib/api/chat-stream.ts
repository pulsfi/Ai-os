/**
 * Streaming client for POST /chat (Server-Sent Events).
 *
 * Axios cannot stream response bodies in the browser, so this uses fetch +
 * ReadableStream directly. Frames from the backend:
 *
 *   data: {"type":"delta","text":"..."}
 *   data: {"type":"done"}
 *   data: {"type":"error","message":"..."}
 */
import { apiBaseUrl } from "@/config/env";
import { ApiError } from "./client";
import type { ApiErrorEnvelope } from "@/types/api";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

interface StreamCallbacks {
  /** Called for every text delta as it arrives. */
  onDelta: (text: string) => void;
}

/**
 * Send the conversation and stream the assistant reply.
 * Resolves with the full reply text; rejects with ApiError on any failure
 * (including a pre-stream JSON error envelope, e.g. "not configured").
 */
export async function streamChat(
  messages: ChatTurn[],
  { onDelta }: StreamCallbacks,
  signal?: AbortSignal,
): Promise<string> {
  const res = await fetch(`${apiBaseUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal,
  }).catch(() => {
    throw new ApiError(
      "Cannot reach the backend. Is it running on the configured URL?",
      "network_error",
      0,
    );
  });

  // Non-SSE response = the standard JSON error envelope (config error, 422…).
  const contentType = res.headers.get("content-type") ?? "";
  if (!res.ok || !contentType.includes("text/event-stream")) {
    let envelope: Partial<ApiErrorEnvelope> | undefined;
    try {
      envelope = (await res.json()) as Partial<ApiErrorEnvelope>;
    } catch {
      // fall through to the generic error below
    }
    throw new ApiError(
      envelope?.error?.message ?? `Chat request failed (${res.status})`,
      envelope?.error?.code ?? "http_error",
      res.status,
      envelope?.error?.details,
    );
  }

  if (!res.body) {
    throw new ApiError("Streaming is not supported by this browser.", "stream_error", 0);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  const handleFrame = (frame: string): void => {
    const line = frame.split("\n").find((l) => l.startsWith("data: "));
    if (!line) return;
    let event: { type: string; text?: string; message?: string };
    try {
      event = JSON.parse(line.slice(6));
    } catch {
      return; // malformed frame — skip rather than kill the stream
    }
    if (event.type === "delta" && event.text) {
      full += event.text;
      onDelta(event.text);
    } else if (event.type === "error") {
      throw new ApiError(event.message ?? "Chat stream failed.", "stream_error", 0);
    }
  };

  // SSE frames are separated by a blank line.
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      handleFrame(frame);
    }
  }

  return full;
}
