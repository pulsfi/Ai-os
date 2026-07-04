/**
 * Typed API services — one function per backend endpoint, all responses
 * Zod-validated. Components never call these directly; they use the
 * TanStack Query hooks in src/hooks.
 */
import { getValidated } from "./client";
import {
  chainStatusSchema,
  healthReportSchema,
  marketStatusSchema,
  systemInfoSchema,
  tokenMarketDataSchema,
  type ChainStatus,
  type HealthReport,
  type MarketStatus,
  type SystemInfo,
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
};

// TODO(backend): WebSocket endpoints for live updates (agent status, logs,
// system metrics, trading events) do not exist yet. When they land, add a
// typed socket client here (src/lib/ws.ts) and replace the polling intervals
// in src/hooks with subscriptions. Per project rule: no fake implementations.
