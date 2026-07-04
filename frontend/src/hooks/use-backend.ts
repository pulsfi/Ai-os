"use client";

/**
 * TanStack Query hooks over the API services — the only way components read
 * backend data. Polling intervals stand in for live updates until the backend
 * exposes WebSocket endpoints (see the TODO in src/lib/api/services.ts).
 */
import { useQuery } from "@tanstack/react-query";

import {
  healthService,
  marketService,
  solanaService,
  systemService,
} from "@/lib/api/services";

/** Query keys — centralized so invalidation stays typo-proof. */
export const qk = {
  health: ["health"] as const,
  systemInfo: ["system", "info"] as const,
  chainStatus: ["solana", "status"] as const,
  marketTokens: ["market", "tokens"] as const,
  marketTrending: ["market", "trending"] as const,
  marketStatus: ["market", "status"] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: healthService.getHealth,
    refetchInterval: 15_000,
  });
}

export function useSystemInfo() {
  return useQuery({
    queryKey: qk.systemInfo,
    queryFn: systemService.getInfo,
    staleTime: Infinity, // identity doesn't change while running
  });
}

export function useChainStatus() {
  return useQuery({
    queryKey: qk.chainStatus,
    queryFn: solanaService.getChainStatus,
    refetchInterval: 10_000,
  });
}

export function useMarketTokens() {
  return useQuery({
    queryKey: qk.marketTokens,
    queryFn: marketService.getTokens,
    refetchInterval: 30_000,
  });
}

export function useMarketStatus() {
  return useQuery({
    queryKey: qk.marketStatus,
    queryFn: marketService.getStatus,
    refetchInterval: 30_000,
  });
}
