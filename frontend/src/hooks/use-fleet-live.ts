"use client";

/**
 * Live fleet state over WebSocket, with the REST poll as fallback.
 *
 * While the socket is healthy the UI updates every ~3s without polling;
 * if it drops, TanStack's 10s poll keeps the data honest until the
 * socket reconnects (capped backoff in src/lib/ws.ts).
 */
import * as React from "react";

import { useBots } from "@/hooks/use-backend";
import { connectFleetSocket } from "@/lib/ws";
import type { BotStatus, BotTrade, FleetSnapshot } from "@/lib/api/schemas";

export interface FleetLive {
  bots: BotStatus[] | undefined;
  trades: BotTrade[] | undefined;
  /** True while the WebSocket is delivering frames. */
  live: boolean;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => void;
}

export function useFleetLive(): FleetLive {
  const poll = useBots();
  const [snapshot, setSnapshot] = React.useState<FleetSnapshot | null>(null);
  const [connected, setConnected] = React.useState(false);

  React.useEffect(() => {
    return connectFleetSocket({
      onSnapshot: setSnapshot,
      onStatus: setConnected,
    });
  }, []);

  const live = connected && snapshot !== null;
  return {
    bots: live ? snapshot.bots : poll.data,
    trades: live ? snapshot.trades : undefined,
    live,
    isLoading: poll.isLoading && !live,
    isError: poll.isError && !live,
    error: poll.error,
    refetch: () => void poll.refetch(),
  };
}
