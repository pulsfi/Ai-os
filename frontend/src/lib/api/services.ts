/**
 * Typed API services — one function per backend endpoint, all responses
 * Zod-validated. Components never call these directly; they use the
 * TanStack Query hooks in src/hooks.
 */
import { getValidated, postValidated } from "./client";
import {
  agentControlResultSchema,
  agentDetailSchema,
  agentReportSchema,
  agentSummarySchema,
  chainStatusSchema,
  chatStatusSchema,
  healthReportSchema,
  historyPointSchema,
  botControlResultSchema,
  botPerformanceSchema,
  botStatusSchema,
  botTradeSchema,
  marketStatusSchema,
  paperSummarySchema,
  paperTradeSchema,
  pumpCoinSchema,
  systemInfoSchema,
  tokenAuthoritiesSchema,
  tokenInfoSchema,
  tokenMarketDataSchema,
  type AgentControlResult,
  type AgentDetail,
  type AgentReport,
  type AgentSummary,
  type ChainStatus,
  type ChatStatus,
  type HealthReport,
  type HistoryPoint,
  type BotControlResult,
  type BotPerformance,
  type BotStatus,
  type BotTrade,
  type MarketStatus,
  type PaperSummary,
  type PaperTrade,
  type PumpCoin,
  type SystemInfo,
  type TokenAuthorities,
  type TokenInfo,
  type TokenMarketData,
} from "./schemas";
import { z } from "zod";

export const healthService = {
  /** GET /health — aggregate system health with per-component probes. */
  getHealth: (): Promise<HealthReport> => getValidated("/health", healthReportSchema),
};

export const systemService = {
  /** GET /system/info — application identity. */
  getInfo: (): Promise<SystemInfo> => getValidated("/system/info", systemInfoSchema),
};

export const solanaService = {
  /** GET /solana/status — live chain snapshot (health, slot, epoch, TPS). */
  getChainStatus: (): Promise<ChainStatus> =>
    getValidated("/solana/status", chainStatusSchema),

  /** GET /solana/token/{mint}/authorities — on-chain rug check. */
  getTokenAuthorities: (mint: string): Promise<TokenAuthorities> =>
    getValidated(
      `/solana/token/${encodeURIComponent(mint)}/authorities`,
      tokenAuthoritiesSchema,
    ),
};

export const marketService = {
  /** GET /market/tokens — merged multi-provider data for the watchlist. */
  getTokens: (): Promise<TokenMarketData[]> =>
    getValidated("/market/tokens", z.array(tokenMarketDataSchema)),

  /** GET /market/trending — watchlist ranked by 24h change. */
  getTrending: (): Promise<TokenMarketData[]> =>
    getValidated("/market/trending", z.array(tokenMarketDataSchema)),

  /** GET /market/status — provider/cache/scheduler monitoring. */
  getStatus: (): Promise<MarketStatus> =>
    getValidated("/market/status", marketStatusSchema),

  /** GET /market/token/{address} — merged data + on-chain metadata. */
  getToken: (address: string): Promise<TokenInfo> =>
    getValidated(`/market/token/${encodeURIComponent(address)}`, tokenInfoSchema),

  /** GET /market/history/{address} — stored snapshots (needs PostgreSQL). */
  getHistory: (address: string, limit = 100): Promise<HistoryPoint[]> =>
    getValidated(
      `/market/history/${encodeURIComponent(address)}?limit=${limit}`,
      z.array(historyPointSchema),
    ),
};

export const pumpfunService = {
  /** GET /market/pumpfun/new — freshest pump.fun launches. */
  getNew: (limit = 20): Promise<PumpCoin[]> =>
    getValidated(`/market/pumpfun/new?limit=${limit}`, z.array(pumpCoinSchema)),

  /** GET /market/pumpfun/graduating — closest to leaving the bonding curve. */
  getGraduating: (limit = 20): Promise<PumpCoin[]> =>
    getValidated(`/market/pumpfun/graduating?limit=${limit}`, z.array(pumpCoinSchema)),
};

export const tradingService = {
  /** GET /trading/summary — paper track record (read-only ledger). */
  getSummary: (): Promise<PaperSummary> =>
    getValidated("/trading/summary", paperSummarySchema),

  /** GET /trading/trades — paper trade log, newest first. */
  getTrades: (limit = 50): Promise<PaperTrade[]> =>
    getValidated(`/trading/trades?limit=${limit}`, z.array(paperTradeSchema)),
};

export const botsService = {
  /** GET /bots — the fleet: config, live state, ledger stats per bot. */
  list: (): Promise<BotStatus[]> => getValidated("/bots", z.array(botStatusSchema)),

  /** GET /bots/performance — equity curves + per-strategy track record. */
  performance: (): Promise<BotPerformance[]> =>
    getValidated("/bots/performance", z.array(botPerformanceSchema)),

  /** GET /bots/trades — fleet-wide paper trade log, newest first. */
  allTrades: (limit = 50): Promise<BotTrade[]> =>
    getValidated(`/bots/trades?limit=${limit}`, z.array(botTradeSchema)),

  /** GET /bots/{id}/trades — one bot's paper trade log. */
  trades: (botId: string, limit = 50): Promise<BotTrade[]> =>
    getValidated(
      `/bots/${encodeURIComponent(botId)}/trades?limit=${limit}`,
      z.array(botTradeSchema),
    ),

  /** POST /bots/{id}/{action} — REAL start/stop/restart of the bot loop. */
  control: (botId: string, action: "start" | "stop" | "restart"): Promise<BotControlResult> =>
    postValidated(
      `/bots/${encodeURIComponent(botId)}/${action}`,
      undefined,
      botControlResultSchema,
    ),
};

export const chatService = {
  /** GET /chat/status — whether the assistant is configured, and its model. */
  getStatus: (): Promise<ChatStatus> => getValidated("/chat/status", chatStatusSchema),
  // Streaming send lives in ./chat-stream.ts (fetch-based SSE reader).
};

export const agentsService = {
  /** GET /agents — pipeline agents with vault-derived status. */
  list: (): Promise<AgentSummary[]> =>
    getValidated("/agents", z.array(agentSummarySchema)),

  /** GET /agents/{name} — full detail (mission, rules, tasks). */
  get: (name: string): Promise<AgentDetail> =>
    getValidated(`/agents/${encodeURIComponent(name)}`, agentDetailSchema),

  /** GET /agents/{name}/reports — report log, newest first. */
  reports: (name: string): Promise<AgentReport[]> =>
    getValidated(`/agents/${encodeURIComponent(name)}/reports`, z.array(agentReportSchema)),

  /**
   * POST /agents/{name}/{action} — start | stop | restart.
   * The backend currently declines with a reason (no runtime until Stage 6);
   * the UI must surface that reason honestly.
   */
  control: (name: string, action: "start" | "stop" | "restart"): Promise<AgentControlResult> =>
    postValidated(
      `/agents/${encodeURIComponent(name)}/${action}`,
      undefined,
      agentControlResultSchema,
    ),
};

// TODO(backend): WebSocket endpoints for live updates (agent status, logs,
// system metrics, trading events) do not exist yet. When they land, add a
// typed socket client here (src/lib/ws.ts) and replace the polling intervals
// in src/hooks with subscriptions. Per project rule: no fake implementations.
