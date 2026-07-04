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
