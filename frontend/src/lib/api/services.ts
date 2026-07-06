/**
 * Typed API services — one function per backend endpoint, all responses
 * Zod-validated. Components never call these directly; they use the
 * TanStack Query hooks in src/hooks.
 */
import { getValidated, patchValidated, postValidated } from "./client";
import {
  agentControlResultSchema,
  agentDetailSchema,
  agentReportSchema,
  agentSummarySchema,
  agentTickSchema,
  runtimeStatusSchema,
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
  type AgentTick,
  type RuntimeStatus,
  type ChainStatus,
  type ChatStatus,
  type HealthReport,
  type HistoryPoint,
  resetResultSchema,
  type BotControlResult,
  type BotPerformance,
  type BotStatus,
  type BotTrade,
  type ResetResult,
  type MarketStatus,
  type PaperSummary,
  type PaperTrade,
  type PumpCoin,
  type SystemInfo,
  alertSchema,
  alertsStatusSchema,
  builtSwapSchema,
  dailyReportResultSchema,
  executionStatusSchema,
  goLiveReadinessSchema,
  liveTradeSchema,
  tokenActivitySchema,
  walletBalanceSchema,
  type Alert,
  type AlertsStatus,
  type BuiltSwap,
  type DailyReportResult,
  type ExecutionStatus,
  type GoLiveReadiness,
  type LiveTrade,
  type TokenActivity,
  type WalletBalance,
  type TokenAuthorities,
  type TokenInfo,
  type TokenMarketData,
  type VaultNote,
  type VaultNoteContent,
  vaultNoteContentSchema,
  vaultNoteSchema,
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

  /** GET /market/activity/{mint} — live buy/sell flow (needs HELIUS_API_KEY). */
  getActivity: (mint: string): Promise<TokenActivity> =>
    getValidated(`/market/activity/${encodeURIComponent(mint)}`, tokenActivitySchema),
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

  /** POST /bots/reset — wipe the paper track record (paper data only). */
  reset: (): Promise<ResetResult> =>
    postValidated("/bots/reset", undefined, resetResultSchema),

  /** PATCH /bots/{id}/config — tune a bot's parameters (paper only). */
  updateConfig: (
    botId: string,
    update: Partial<{
      usd_per_trade: number;
      max_open_positions: number;
      take_profit_pct: number;
      stop_loss_pct: number;
      trail_after_pct: number;
      trail_drop_pct: number;
      interval_s: number;
      exit_slippage_bps: number;
      max_gain_pct: number;
      reentry_cooldown_s: number;
    }>,
  ): Promise<BotStatus> =>
    patchValidated(`/bots/${encodeURIComponent(botId)}/config`, update, botStatusSchema),
};

export const executionService = {
  /** GET /execution/status — armed?, mode, limits, kill switch, day PnL. */
  status: (): Promise<ExecutionStatus> =>
    getValidated("/execution/status", executionStatusSchema),

  /** GET /execution/readiness — go-live scorecard vs the paper record. */
  readiness: (): Promise<GoLiveReadiness> =>
    getValidated("/execution/readiness", goLiveReadinessSchema),

  /** POST /execution/kill/{on|off} — global halt (can only stop execution). */
  setKill: (on: boolean): Promise<ExecutionStatus> =>
    postValidated(`/execution/kill/${on ? "on" : "off"}`, undefined, executionStatusSchema),

  /** POST /execution/mode/{paper|live} — switch mode. Live is gated by the
   *  readiness scorecard (throws 409 not_ready_for_live until green). */
  setMode: (mode: "paper" | "live"): Promise<ExecutionStatus> =>
    postValidated(`/execution/mode/${mode}`, undefined, executionStatusSchema),

  /** GET /execution/wallet/{pubkey}/balance — read-only SOL balance. */
  walletBalance: (pubkey: string): Promise<WalletBalance> =>
    getValidated(`/execution/wallet/${encodeURIComponent(pubkey)}/balance`, walletBalanceSchema),

  /** POST /execution/trade/build-buy — UNSIGNED SOL→token buy for Phantom. */
  buildBuy: (userPubkey: string, mint: string, usdSize: number): Promise<BuiltSwap> =>
    postValidated(
      "/execution/trade/build-buy",
      { user_pubkey: userPubkey, mint, usd_size: usdSize },
      builtSwapSchema,
    ),

  /** POST /execution/trade/build-sell — UNSIGNED token→SOL full-balance sell. */
  buildSell: (userPubkey: string, mint: string): Promise<BuiltSwap> =>
    postValidated(
      "/execution/trade/build-sell",
      { user_pubkey: userPubkey, mint },
      builtSwapSchema,
    ),

  /** POST /execution/trade/record — record + reconcile a Phantom-signed trade. */
  recordTrade: (t: {
    signature: string;
    wallet: string;
    mint: string;
    symbol: string;
    side: "buy" | "sell";
    usd_size: number;
  }): Promise<LiveTrade> => postValidated("/execution/trade/record", t, liveTradeSchema),

  /** GET /execution/trades — your real wallet trades, newest first. */
  liveTrades: (): Promise<LiveTrade[]> =>
    getValidated("/execution/trades", z.array(liveTradeSchema)),
};

export const alertsService = {
  /** GET /alerts — recent alerts + telegram config flag. */
  list: (): Promise<AlertsStatus> => getValidated("/alerts", alertsStatusSchema),
  /** POST /alerts/test — emit a test alert. */
  test: (): Promise<Alert> => postValidated("/alerts/test", undefined, alertSchema),
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

  /** GET /agents/runtime — live pipeline status + activity feed (Stage 6). */
  runtime: (): Promise<RuntimeStatus> =>
    getValidated("/agents/runtime", runtimeStatusSchema),

  /** GET /agents/{name}/activity — the agent's live pipeline output. */
  activity: (name: string): Promise<AgentTick[]> =>
    getValidated(`/agents/${encodeURIComponent(name)}/activity`, z.array(agentTickSchema)),

  /** POST /agents/{name}/{action} — REAL start/stop/restart in the pipeline. */
  control: (name: string, action: "start" | "stop" | "restart"): Promise<AgentControlResult> =>
    postValidated(
      `/agents/${encodeURIComponent(name)}/${action}`,
      undefined,
      agentControlResultSchema,
    ),
};

export const vaultService = {
  /** GET /vault/dirs — folders the backend exposes (allowlist). */
  dirs: (): Promise<string[]> => getValidated("/vault/dirs", z.array(z.string())),

  /** GET /vault/notes — markdown notes in one folder, newest first. */
  notes: (dir: string): Promise<VaultNote[]> =>
    getValidated(`/vault/notes?dir=${encodeURIComponent(dir)}`, z.array(vaultNoteSchema)),

  /** GET /vault/note — one note's full markdown. */
  note: (path: string): Promise<VaultNoteContent> =>
    getValidated(`/vault/note?path=${encodeURIComponent(path)}`, vaultNoteContentSchema),

  /** POST /vault/daily-report — append the fleet report to today's note. */
  writeDailyReport: (): Promise<DailyReportResult> =>
    postValidated("/vault/daily-report", undefined, dailyReportResultSchema),
};

// Live updates: the bot fleet streams over ws://…/api/v1/ws (src/lib/ws.ts).
// Other domains (agents, chat presence, system metrics) still poll — extend
// the WS payload before adding sockets for them. No fake implementations.
