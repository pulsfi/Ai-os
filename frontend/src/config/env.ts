/**
 * Typed, validated runtime configuration.
 *
 * Client-exposed values must be prefixed NEXT_PUBLIC_ (Next.js requirement).
 * Zod validates them at module load so a misconfigured deployment fails
 * loudly at startup rather than mid-request. Defaults point at the local
 * FastAPI backend so `npm run dev` works with zero setup.
 */
import { z } from "zod";

const schema = z.object({
  /** FastAPI base URL, e.g. http://127.0.0.1:8000 (no trailing slash). */
  NEXT_PUBLIC_API_URL: z.string().url().default("http://127.0.0.1:8000"),
  /** Versioned API prefix mounted by the backend. */
  NEXT_PUBLIC_API_PREFIX: z.string().default("/api/v1"),
  /** WebSocket base URL for live updates (ws:// or wss://). */
  NEXT_PUBLIC_WS_URL: z.string().default("ws://127.0.0.1:8000"),
});

/**
 * `process.env` keys must be referenced statically for Next.js to inline
 * NEXT_PUBLIC_* values into the client bundle — no dynamic access.
 */
const parsed = schema.safeParse({
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_API_PREFIX: process.env.NEXT_PUBLIC_API_PREFIX,
  NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
});

if (!parsed.success) {
  // Surface the exact misconfigured variables at boot.
  throw new Error(
    `Invalid environment configuration:\n${parsed.error.issues
      .map((i) => `  ${i.path.join(".")}: ${i.message}`)
      .join("\n")}`,
  );
}

export const env = parsed.data;

/** Full REST base, e.g. http://127.0.0.1:8000/api/v1. */
export const apiBaseUrl = `${env.NEXT_PUBLIC_API_URL}${env.NEXT_PUBLIC_API_PREFIX}`;
