"use client";

/**
 * TanStack Query hooks over the API services — the only way components read
 * backend data. Polling intervals stand in for live updates until the backend
 * exposes WebSocket endpoints (see the TODO in src/lib/api/services.ts).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  agentsService,
  alertsService,
  botsService,
  chatService,
  executionService,
  healthService,
  marketService,
  pumpfunService,
  solanaService,
  systemService,
  tradingService,
  vaultService,
} from "@/lib/api/services";

/** Query keys — centralized so invalidation stays typo-proof. */
export const qk = {
  health: ["health"] as const,
  systemInfo: ["system", "info"] as const,
  chainStatus: ["solana", "status"] as const,
  tokenAuthorities: (mint: string) => ["solana", "authorities", mint] as const,
  marketTokens: ["market", "tokens"] as const,
  marketTrending: ["market", "trending"] as const,
  marketStatus: ["market", "status"] as const,
  marketToken: (address: string) => ["market", "token", address] as const,
  tokenActivity: (mint: string) => ["market", "activity", mint] as const,
  marketHistory: (address: string) => ["market", "history", address] as const,
  chatStatus: ["chat", "status"] as const,
  pumpfunNew: ["pumpfun", "new"] as const,
  pumpfunGraduating: ["pumpfun", "graduating"] as const,
  paperSummary: ["trading", "summary"] as const,
  paperTrades: ["trading", "trades"] as const,
  bots: ["bots"] as const,
  botTrades: (botId: string | null) => ["bots", "trades", botId ?? "all"] as const,
  botPerformance: ["bots", "performance"] as const,
  vaultDirs: ["vault", "dirs"] as const,
  vaultNotes: (dir: string) => ["vault", "notes", dir] as const,
  vaultNote: (path: string) => ["vault", "note", path] as const,
  agents: ["agents"] as const,
  agent: (name: string) => ["agents", name] as const,
  agentReports: (name: string) => ["agents", name, "reports"] as const,
  agentRuntime: ["agents", "runtime"] as const,
  agentActivity: (name: string) => ["agents", name, "activity"] as const,
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

export function useMarketTrending() {
  return useQuery({
    queryKey: qk.marketTrending,
    queryFn: marketService.getTrending,
    refetchInterval: 30_000,
  });
}

/** Single-token lookup — enabled only when an address is entered. */
export function useMarketToken(address: string) {
  return useQuery({
    queryKey: qk.marketToken(address),
    queryFn: () => marketService.getToken(address),
    enabled: address.length > 0,
    retry: false, // a bad address should fail once, not three times
  });
}

export function useMarketHistory(address: string, limit = 100) {
  return useQuery({
    queryKey: qk.marketHistory(address),
    queryFn: () => marketService.getHistory(address, limit),
    enabled: address.length > 0,
    retry: false, // history requires PostgreSQL; surface that immediately
  });
}

/** Live buy/sell flow via Helius — enabled when a mint is entered. */
export function useTokenActivity(mint: string) {
  return useQuery({
    queryKey: qk.tokenActivity(mint),
    queryFn: () => marketService.getActivity(mint),
    enabled: mint.length > 0,
    retry: false, // "not configured" should surface once, immediately
    refetchInterval: 30_000,
  });
}

/** On-chain mint/freeze authority check — enabled when a mint is entered. */
export function useTokenAuthorities(mint: string) {
  return useQuery({
    queryKey: qk.tokenAuthorities(mint),
    queryFn: () => solanaService.getTokenAuthorities(mint),
    enabled: mint.length > 0,
    retry: false,
  });
}

/** Fresh pump.fun launches — fast-moving, poll every 15s. */
export function usePumpfunNew(limit = 12) {
  return useQuery({
    queryKey: qk.pumpfunNew,
    queryFn: () => pumpfunService.getNew(limit),
    refetchInterval: 15_000,
  });
}

export function usePumpfunGraduating(limit = 12) {
  return useQuery({
    queryKey: qk.pumpfunGraduating,
    queryFn: () => pumpfunService.getGraduating(limit),
    refetchInterval: 30_000,
  });
}

export function usePaperSummary() {
  return useQuery({
    queryKey: qk.paperSummary,
    queryFn: tradingService.getSummary,
    refetchInterval: 30_000,
  });
}

export function usePaperTrades(limit = 50) {
  return useQuery({
    queryKey: qk.paperTrades,
    queryFn: () => tradingService.getTrades(limit),
    refetchInterval: 30_000,
  });
}

export function useExecutionStatus() {
  return useQuery({
    queryKey: ["execution", "status"] as const,
    queryFn: executionService.status,
    refetchInterval: 15_000,
  });
}

export function useGoLiveReadiness() {
  return useQuery({
    queryKey: ["execution", "readiness"] as const,
    queryFn: executionService.readiness,
    refetchInterval: 60_000,
  });
}

/** Global kill switch — refreshes execution status on toggle. */
export function useKillSwitch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (on: boolean) => executionService.setKill(on),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["execution"] });
    },
  });
}

/** Your real (Phantom-signed) wallet trades, reconciled on-chain. */
export function useLiveTrades() {
  return useQuery({
    queryKey: ["execution", "trades"] as const,
    queryFn: executionService.liveTrades,
    refetchInterval: 15_000,
  });
}

/** Record a Phantom-signed trade so it gets reconciled + shown. */
export function useRecordTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: executionService.recordTrade,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["execution", "trades"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

/** Recent alerts feed (in-app; Telegram fires too when configured). */
export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"] as const,
    queryFn: alertsService.list,
    refetchInterval: 12_000,
  });
}

export function useTestAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: alertsService.test,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

/** Paper⇄Live switch — live is gated server-side by the readiness scorecard. */
export function useSetTradingMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mode: "paper" | "live") => executionService.setMode(mode),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["execution"] });
    },
  });
}

/** The bot fleet — live loops, so poll fast (10s). */
export function useBots() {
  return useQuery({
    queryKey: qk.bots,
    queryFn: botsService.list,
    refetchInterval: 10_000,
  });
}

/** One bot's trades (or the whole fleet's when botId is null). */
export function useBotTrades(botId: string | null, limit = 50) {
  return useQuery({
    queryKey: qk.botTrades(botId),
    queryFn: () =>
      botId === null ? botsService.allTrades(limit) : botsService.trades(botId, limit),
    refetchInterval: 15_000,
  });
}

/** Wipe the paper track record — refreshes every bot view. */
export function useResetLedger() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: botsService.reset,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.bots });
      void queryClient.invalidateQueries({ queryKey: qk.botPerformance });
      void queryClient.invalidateQueries({ queryKey: ["execution"] });
    },
  });
}

/** Track record: equity curves + per-strategy comparison. */
export function useBotPerformance() {
  return useQuery({
    queryKey: qk.botPerformance,
    queryFn: botsService.performance,
    refetchInterval: 30_000,
  });
}

/** REAL start/stop/restart — refreshes the fleet list on success. */
export function useBotControl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ botId, action }: { botId: string; action: "start" | "stop" | "restart" }) =>
      botsService.control(botId, action),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.bots });
    },
  });
}

export function useChatStatus() {
  return useQuery({
    queryKey: qk.chatStatus,
    queryFn: chatService.getStatus,
    staleTime: 60_000,
  });
}

/** Write today's fleet report into the daily note; refresh note lists. */
export function useWriteDailyReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: vaultService.writeDailyReport,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["vault"] });
    },
  });
}

export function useVaultDirs() {
  return useQuery({
    queryKey: qk.vaultDirs,
    queryFn: vaultService.dirs,
    staleTime: 5 * 60_000, // the allowlist changes only with deployments
  });
}

export function useVaultNotes(dir: string) {
  return useQuery({
    queryKey: qk.vaultNotes(dir),
    queryFn: () => vaultService.notes(dir),
    enabled: dir.length > 0,
  });
}

export function useVaultNote(path: string) {
  return useQuery({
    queryKey: qk.vaultNote(path),
    queryFn: () => vaultService.note(path),
    enabled: path.length > 0,
  });
}

export function useAgents() {
  return useQuery({
    queryKey: qk.agents,
    queryFn: agentsService.list,
    refetchInterval: 10_000, // live pipeline — refresh often
  });
}

export function useAgentRuntime() {
  return useQuery({
    queryKey: qk.agentRuntime,
    queryFn: agentsService.runtime,
    refetchInterval: 8_000,
  });
}

export function useAgentActivity(name: string) {
  return useQuery({
    queryKey: qk.agentActivity(name),
    queryFn: () => agentsService.activity(name),
    enabled: name.length > 0,
    refetchInterval: 8_000,
  });
}

export function useAgent(name: string) {
  return useQuery({
    queryKey: qk.agent(name),
    queryFn: () => agentsService.get(name),
    enabled: name.length > 0,
  });
}

export function useAgentReports(name: string) {
  return useQuery({
    queryKey: qk.agentReports(name),
    queryFn: () => agentsService.reports(name),
    enabled: name.length > 0,
  });
}

/** start/stop/restart — backend answers honestly (declined until Stage 6). */
export function useAgentControl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, action }: { name: string; action: "start" | "stop" | "restart" }) =>
      agentsService.control(name, action),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.agents });
      void queryClient.invalidateQueries({ queryKey: qk.agentRuntime });
    },
  });
}
