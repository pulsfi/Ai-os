/**
 * Zod schemas mirroring the FastAPI response contracts
 * (backend/models/schemas + modules/market/market_models.py).
 * Types are inferred from these — one source of truth on the client.
 */
import { z } from "zod";

// --- health -----------------------------------------------------------

export const healthStatusSchema = z.enum(["ok", "degraded", "down"]);

export const componentStatusSchema = z.object({
  name: z.string(),
  status: healthStatusSchema,
  latency_ms: z.number().nullable(),
  detail: z.string().nullable(),
});

export const healthReportSchema = z.object({
  status: healthStatusSchema,
  version: z.string(),
  environment: z.string(),
  components: z.array(componentStatusSchema),
});

export type HealthReport = z.infer<typeof healthReportSchema>;
export type ComponentStatus = z.infer<typeof componentStatusSchema>;

// --- system -----------------------------------------------------------

export const systemInfoSchema = z.object({
  app_name: z.string(),
  version: z.string(),
  environment: z.string(),
  debug: z.boolean(),
});

export type SystemInfo = z.infer<typeof systemInfoSchema>;

// --- solana -----------------------------------------------------------

export const epochInfoSchema = z.object({
  epoch: z.number(),
  slot_index: z.number(),
  slots_in_epoch: z.number(),
  absolute_slot: z.number(),
  progress_pct: z.number(),
});

export const chainStatusSchema = z.object({
  healthy: z.boolean(),
  slot: z.number().nullable(),
  epoch: epochInfoSchema.nullable(),
  tps: z.number().nullable(),
});

export type ChainStatus = z.infer<typeof chainStatusSchema>;

// --- market -----------------------------------------------------------

export const tradingPairSchema = z.object({
  dex: z.string(),
  pair_address: z.string().nullable(),
  base_symbol: z.string().nullable(),
  quote_symbol: z.string().nullable(),
  price_usd: z.number().nullable(),
  liquidity_usd: z.number().nullable(),
});

export const tokenMarketDataSchema = z.object({
  mint: z.string(),
  symbol: z.string().nullable(),
  price_usd: z.number().nullable(),
  change_24h: z.number().nullable(),
  volume_24h: z.number().nullable(),
  liquidity_usd: z.number().nullable(),
  market_cap: z.number().nullable(),
  fdv: z.number().nullable(),
  dex: z.string().nullable(),
  pairs: z.array(tradingPairSchema),
  sources: z.array(z.string()),
  divergence_pct: z.number().nullable(),
  fetched_at: z.string(),
});

export type TokenMarketData = z.infer<typeof tokenMarketDataSchema>;

export const providerStatusSchema = z.object({
  name: z.string(),
  configured: z.boolean(),
  calls: z.number(),
  errors: z.number(),
  avg_latency_ms: z.number().nullable(),
  last_success: z.string().nullable(),
  last_error: z.string().nullable(),
});

export const marketStatusSchema = z.object({
  providers: z.array(providerStatusSchema),
  cache_backend: z.string(),
  cache_hits: z.number(),
  cache_misses: z.number(),
  scheduler_enabled: z.boolean(),
  scheduler_interval_s: z.number(),
  scheduler_runs: z.number(),
  last_refresh: z.string().nullable(),
  tracked_tokens: z.number(),
});

export type MarketStatus = z.infer<typeof marketStatusSchema>;
export type ProviderStatus = z.infer<typeof providerStatusSchema>;

// --- solana: token authorities (rug check) ------------------------------

export const tokenAuthoritiesSchema = z.object({
  mint_authority: z.string().nullable(),
  freeze_authority: z.string().nullable(),
  is_fully_revoked: z.boolean(),
});

export type TokenAuthorities = z.infer<typeof tokenAuthoritiesSchema>;

// --- market: single token + history -------------------------------------

export const tokenInfoSchema = z.object({
  market: tokenMarketDataSchema,
  decimals: z.number().nullable(),
  supply_ui: z.number().nullable(),
  authorities: tokenAuthoritiesSchema.nullable(),
});

export type TokenInfo = z.infer<typeof tokenInfoSchema>;

export const historyPointSchema = z.object({
  ts: z.string(),
  price_usd: z.number().nullable(),
  change_24h: z.number().nullable(),
  volume_24h: z.number().nullable(),
  liquidity_usd: z.number().nullable(),
  market_cap: z.number().nullable(),
  fdv: z.number().nullable(),
  sources: z.string().nullable(),
});

export type HistoryPoint = z.infer<typeof historyPointSchema>;

// --- chat ----------------------------------------------------------------

export const chatStatusSchema = z.object({
  configured: z.boolean(),
  model: z.string(),
});

export type ChatStatus = z.infer<typeof chatStatusSchema>;

// --- agents ----------------------------------------------------------------

export const agentSummarySchema = z.object({
  name: z.string(),
  status: z.string(),
  created: z.string().nullable(),
  description: z.string(),
  report_count: z.number(),
  last_report_date: z.string().nullable(),
  last_activity: z.string().nullable(),
  runtime_state: z.string(),
  last_run: z.string().nullable(),
  last_summary: z.string().nullable(),
  last_ok: z.boolean().nullable(),
  cycles: z.number(),
});

export type AgentSummary = z.infer<typeof agentSummarySchema>;

export const agentDetailSchema = agentSummarySchema.extend({
  mission: z.string(),
  rules: z.string(),
  tasks: z.string(),
});

export type AgentDetail = z.infer<typeof agentDetailSchema>;

export const agentReportSchema = z.object({
  title: z.string(),
  date: z.string(),
  body: z.string(),
});

export type AgentReport = z.infer<typeof agentReportSchema>;

export const agentControlResultSchema = z.object({
  agent: z.string(),
  action: z.string(),
  accepted: z.boolean(),
  reason: z.string(),
  runtime_state: z.string(),
});

export type AgentControlResult = z.infer<typeof agentControlResultSchema>;

export const agentTickSchema = z.object({
  agent: z.string(),
  ts: z.string(),
  ok: z.boolean(),
  summary: z.string(),
  detail: z.string(),
});

export type AgentTick = z.infer<typeof agentTickSchema>;

export const runtimeAgentStatusSchema = z.object({
  name: z.string(),
  enabled: z.boolean(),
  runtime_state: z.string(),
  runs: z.number(),
  last_run: z.string().nullable(),
  last_summary: z.string().nullable(),
  last_ok: z.boolean().nullable(),
});

export const runtimeStatusSchema = z.object({
  running: z.boolean(),
  cycle_seconds: z.number(),
  cycles: z.number(),
  started_at: z.string().nullable(),
  agents: z.array(runtimeAgentStatusSchema),
  recent: z.array(agentTickSchema),
});

export type RuntimeStatus = z.infer<typeof runtimeStatusSchema>;

// --- pump.fun discovery ----------------------------------------------------

export const pumpCoinSchema = z.object({
  mint: z.string(),
  name: z.string(),
  symbol: z.string(),
  created_at: z.string(),
  usd_market_cap: z.number().nullable(),
  reply_count: z.number(),
  complete: z.boolean(),
  bonding_progress_pct: z.number(),
  is_currently_live: z.boolean(),
  creator: z.string().nullable(),
  creator_username: z.string().nullable(),
  image_uri: z.string().nullable(),
});

export type PumpCoin = z.infer<typeof pumpCoinSchema>;

// --- paper trading (read-only ledger) ---------------------------------------

export const paperTradeSchema = z.object({
  id: z.number(),
  symbol: z.string(),
  mint: z.string().nullable(),
  usd_size: z.number(),
  entry_price: z.number(),
  entry_ts: z.string(),
  exit_price: z.number().nullable(),
  exit_ts: z.string().nullable(),
  pnl_usd: z.number().nullable(),
  pnl_pct: z.number().nullable(),
  reasoning: z.string().nullable(),
  exit_note: z.string().nullable(),
  status: z.string(),
});

export type PaperTrade = z.infer<typeof paperTradeSchema>;

export const paperSummarySchema = z.object({
  available: z.boolean(),
  total_trades: z.number(),
  open_trades: z.number(),
  closed_trades: z.number(),
  realized_pnl_usd: z.number(),
  win_rate_pct: z.number().nullable(),
  last_entry_ts: z.string().nullable(),
  snapshots_stored: z.number(),
});

export type PaperSummary = z.infer<typeof paperSummarySchema>;

// --- bot fleet (paper-mode runtime with REAL controls) -----------------------

export const botStateSchema = z.enum(["stopped", "running", "error"]);

export const botConfigSchema = z.object({
  id: z.string(),
  name: z.string(),
  strategy: z.string(),
  description: z.string(),
  interval_s: z.number(),
  usd_per_trade: z.number(),
  max_open_positions: z.number(),
  take_profit_pct: z.number(),
  stop_loss_pct: z.number(),
  max_hold_s: z.number(),
  trail_after_pct: z.number().nullable(),
  trail_drop_pct: z.number().nullable(),
  break_even_at_pct: z.number().nullable().optional(),
  exit_slippage_bps: z.number(),
  max_gain_pct: z.number(),
  reentry_cooldown_s: z.number(),
  one_shot_per_mint: z.boolean(),
});

export const botStatusSchema = z.object({
  config: botConfigSchema,
  state: botStateSchema,
  started_at: z.string().nullable(),
  ticks: z.number(),
  errors: z.number(),
  last_error: z.string().nullable(),
  open_positions: z.number(),
  closed_trades: z.number(),
  realized_pnl_usd: z.number(),
  win_rate_pct: z.number().nullable(),
  // Expectancy-guard pause reason (None = trading normally).
  risk_note: z.string().nullable().optional(),
});

export type BotStatus = z.infer<typeof botStatusSchema>;
export type BotState = z.infer<typeof botStateSchema>;

export const botTradeSchema = z.object({
  id: z.number(),
  bot_id: z.string(),
  mint: z.string(),
  symbol: z.string(),
  usd_size: z.number(),
  entry_price: z.number(),
  entry_ts: z.string(),
  exit_price: z.number().nullable(),
  exit_ts: z.string().nullable(),
  pnl_usd: z.number().nullable(),
  pnl_pct: z.number().nullable(),
  status: z.string(),
  entry_note: z.string().nullable(),
  exit_note: z.string().nullable(),
});

export type BotTrade = z.infer<typeof botTradeSchema>;

export const botControlResultSchema = z.object({
  bot_id: z.string(),
  action: z.string(),
  accepted: z.boolean(),
  state: botStateSchema,
  detail: z.string(),
});

export type BotControlResult = z.infer<typeof botControlResultSchema>;

export const equityPointSchema = z.object({
  ts: z.string(),
  equity_usd: z.number(),
});

export const botPerformanceSchema = z.object({
  bot_id: z.string(),
  name: z.string(),
  closed_trades: z.number(),
  wins: z.number(),
  losses: z.number(),
  win_rate_pct: z.number().nullable(),
  realized_pnl_usd: z.number(),
  avg_pnl_pct: z.number().nullable(),
  best_trade_pct: z.number().nullable(),
  worst_trade_pct: z.number().nullable(),
  // Long-term viability metrics (win rate alone lies):
  profit_factor: z.number().nullable().optional(),
  expectancy_usd: z.number().nullable().optional(),
  avg_win_pct: z.number().nullable().optional(),
  avg_loss_pct: z.number().nullable().optional(),
  max_drawdown_usd: z.number().nullable().optional(),
  today_pnl_usd: z.number().optional(),
  curve: z.array(equityPointSchema),
});

export type BotPerformance = z.infer<typeof botPerformanceSchema>;
export type EquityPoint = z.infer<typeof equityPointSchema>;

export const resetResultSchema = z.object({
  wiped: z.number(),
  detail: z.string(),
});

export type ResetResult = z.infer<typeof resetResultSchema>;

/** One frame pushed by ws://…/api/v1/ws every few seconds. */
export const fleetSnapshotSchema = z.object({
  type: z.literal("fleet"),
  ts: z.string(),
  bots: z.array(botStatusSchema),
  trades: z.array(botTradeSchema),
});

export type FleetSnapshot = z.infer<typeof fleetSnapshotSchema>;

// --- vault notes (read-only) ---------------------------------------------

export const vaultNoteSchema = z.object({
  name: z.string(),
  path: z.string(),
  modified: z.string(),
  size_bytes: z.number(),
});

export type VaultNote = z.infer<typeof vaultNoteSchema>;

export const vaultNoteContentSchema = z.object({
  name: z.string(),
  path: z.string(),
  content: z.string(),
  modified: z.string(),
});

export type VaultNoteContent = z.infer<typeof vaultNoteContentSchema>;

export const dailyReportResultSchema = z.object({
  path: z.string(),
  written: z.boolean(),
});

export type DailyReportResult = z.infer<typeof dailyReportResultSchema>;

// --- token activity (Helius Enhanced; key-gated) ----------------------------

export const tokenActivitySchema = z.object({
  mint: z.string(),
  sampled_txs: z.number(),
  swaps: z.number(),
  buys: z.number(),
  sells: z.number(),
  buy_ratio_pct: z.number().nullable(),
  unique_wallets: z.number(),
  txs_per_minute: z.number().nullable(),
  first_ts: z.string().nullable(),
  last_ts: z.string().nullable(),
});

export type TokenActivity = z.infer<typeof tokenActivitySchema>;

// --- AI confidence score (the Decision Card engine) ------------------------

export const scoreFactorSchema = z.object({
  name: z.string(),
  points: z.number(),
  max_points: z.number(),
  detail: z.string(),
});

export const tokenScoreSchema = z.object({
  mint: z.string(),
  score: z.number(),
  approved: z.boolean(),
  factors: z.array(scoreFactorSchema),
  rejects: z.array(z.string()),
  buy_ratio_pct: z.number().nullable(),
  unique_wallets: z.number().nullable(),
  liquidity_usd: z.number().nullable(),
  market_cap: z.number().nullable(),
  mint_revoked: z.boolean().nullable(),
  freeze_revoked: z.boolean().nullable(),
});

export type TokenScore = z.infer<typeof tokenScoreSchema>;
export type ScoreFactor = z.infer<typeof scoreFactorSchema>;

// --- execution layer (Stage 5; ships disarmed) ------------------------------

export const riskLimitsSchema = z.object({
  max_position_usd: z.number(),
  daily_loss_limit_usd: z.number(),
  max_concurrent_positions: z.number(),
  max_slippage_bps: z.number(),
});

export const executionStatusSchema = z.object({
  armed: z.boolean(),
  mode: z.string(),
  kill_switch: z.boolean(),
  live_available: z.boolean(),
  limits: riskLimitsSchema,
  realized_pnl_today_usd: z.number(),
  reason: z.string(),
});

export type ExecutionStatus = z.infer<typeof executionStatusSchema>;

export const readinessCriterionSchema = z.object({
  name: z.string(),
  target: z.string(),
  actual: z.string(),
  passed: z.boolean(),
});

export const goLiveReadinessSchema = z.object({
  ready: z.boolean(),
  criteria: z.array(readinessCriterionSchema),
  summary: z.string(),
});

export type GoLiveReadiness = z.infer<typeof goLiveReadinessSchema>;

// --- manual wallet trading (Phantom-signed) ---------------------------------

export const walletBalanceSchema = z.object({
  address: z.string(),
  sol: z.number(),
  lamports: z.number(),
});

export type WalletBalance = z.infer<typeof walletBalanceSchema>;

export const builtSwapSchema = z.object({
  swap_transaction_b64: z.string(),
  description: z.string(),
  price_impact_pct: z.number().nullable(),
  out_amount: z.string().nullable(),
  warning: z.string(),
});

export type BuiltSwap = z.infer<typeof builtSwapSchema>;

export const liveTradeSchema = z.object({
  id: z.number(),
  signature: z.string(),
  wallet: z.string(),
  mint: z.string(),
  symbol: z.string(),
  side: z.string(),
  usd_size: z.number(),
  status: z.string(),
  submitted_ts: z.string(),
  confirmed_ts: z.string().nullable(),
});

export type LiveTrade = z.infer<typeof liveTradeSchema>;

// --- alerts ------------------------------------------------------------------

export const alertSchema = z.object({
  level: z.enum(["info", "warning", "critical"]),
  title: z.string(),
  message: z.string(),
  ts: z.string(),
});

export type Alert = z.infer<typeof alertSchema>;

export const alertsStatusSchema = z.object({
  telegram_configured: z.boolean(),
  alerts: z.array(alertSchema),
});

export type AlertsStatus = z.infer<typeof alertsStatusSchema>;
