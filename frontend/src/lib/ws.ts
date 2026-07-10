/**
 * Typed WebSocket client for the backend's live fleet stream.
 *
 * Frames are Zod-validated like every REST response — a malformed frame
 * is dropped (and logged), never rendered. Reconnects with capped
 * exponential backoff so a backend restart heals itself.
 */
import { env } from "@/config/env";
import { fleetSnapshotSchema, type FleetSnapshot } from "@/lib/api/schemas";
import { authToken } from "@/lib/auth";

const WS_BASE = `${env.NEXT_PUBLIC_WS_URL}${env.NEXT_PUBLIC_API_PREFIX}/ws`;

export interface FleetSocketHandlers {
  onSnapshot: (snapshot: FleetSnapshot) => void;
  onStatus: (connected: boolean) => void;
}

/** Open the stream; returns a cleanup that stops reconnecting and closes. */
export function connectFleetSocket({ onSnapshot, onStatus }: FleetSocketHandlers): () => void {
  let socket: WebSocket | null = null;
  let retryMs = 1_000;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  function open() {
    if (closed) return;
    // Browsers can't set WS headers, so the token rides in the query string.
    const token = authToken.get();
    socket = new WebSocket(token ? `${WS_BASE}?token=${encodeURIComponent(token)}` : WS_BASE);

    socket.onopen = () => {
      retryMs = 1_000; // healthy again — reset backoff
      onStatus(true);
    };

    socket.onmessage = (event) => {
      let raw: unknown;
      try {
        raw = JSON.parse(event.data as string);
      } catch {
        return;
      }
      const parsed = fleetSnapshotSchema.safeParse(raw);
      if (parsed.success) {
        onSnapshot(parsed.data);
      } else {
        console.warn("ws: dropped malformed fleet frame", parsed.error.issues);
      }
    };

    socket.onclose = () => {
      onStatus(false);
      if (closed) return;
      timer = setTimeout(open, retryMs);
      retryMs = Math.min(retryMs * 2, 15_000);
    };

    socket.onerror = () => {
      socket?.close(); // funnel everything through onclose/backoff
    };
  }

  open();

  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    socket?.close();
  };
}
