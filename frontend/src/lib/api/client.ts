/**
 * Shared HTTP client for the FastAPI backend.
 *
 * - Base URL from validated env config (src/config/env.ts).
 * - Normalizes the backend's single error envelope
 *   {"error": {code, message, details}} into a typed ApiError, so hooks and
 *   components never touch raw Axios errors.
 * - Generous timeout: a cold /market/tokens sweep paces providers (~1s per
 *   token) before the cache warms.
 */
import axios, { AxiosError } from "axios";
import type { ZodType } from "zod";

import { apiBaseUrl } from "@/config/env";
import { authToken } from "@/lib/auth";
import type { ApiErrorEnvelope } from "@/types/api";

export class ApiError extends Error {
  constructor(
    message: string,
    /** Backend error code (e.g. "external_service_error") or a client code. */
    public readonly code: string,
    /** HTTP status, 0 when the request never reached the server. */
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const http = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30_000,
  headers: { Accept: "application/json" },
});

// Attach the API token (if the user has logged in) to every request.
http.interceptors.request.use((config) => {
  const token = authToken.get();
  if (token) config.headers.set("X-API-Key", token);
  return config;
});

http.interceptors.response.use(undefined, (error: AxiosError) => {
  const envelope = error.response?.data as Partial<ApiErrorEnvelope> | undefined;
  if (envelope?.error?.message) {
    throw new ApiError(
      envelope.error.message,
      envelope.error.code ?? "unknown_error",
      error.response?.status ?? 0,
      envelope.error.details,
    );
  }
  if (error.code === "ECONNABORTED") {
    throw new ApiError("The backend did not respond in time.", "timeout", 0);
  }
  if (!error.response) {
    throw new ApiError(
      "Cannot reach the backend. Is it running on the configured URL?",
      "network_error",
      0,
    );
  }
  throw new ApiError(error.message, "http_error", error.response.status);
});

/**
 * GET + Zod-validate. Every service goes through this so a backend contract
 * drift fails loudly (and typed) instead of rendering garbage.
 */
export async function getValidated<T>(url: string, schema: ZodType<T>): Promise<T> {
  const res = await http.get(url);
  const parsed = schema.safeParse(res.data);
  if (!parsed.success) {
    throw new ApiError(
      `Unexpected response shape from ${url}`,
      "contract_mismatch",
      res.status,
      parsed.error.issues,
    );
  }
  return parsed.data;
}

/** POST + Zod-validate — same contract-drift guarantee as getValidated. */
export async function postValidated<T>(
  url: string,
  body: unknown,
  schema: ZodType<T>,
): Promise<T> {
  const res = await http.post(url, body);
  const parsed = schema.safeParse(res.data);
  if (!parsed.success) {
    throw new ApiError(
      `Unexpected response shape from ${url}`,
      "contract_mismatch",
      res.status,
      parsed.error.issues,
    );
  }
  return parsed.data;
}

/** PATCH + Zod-validate. */
export async function patchValidated<T>(
  url: string,
  body: unknown,
  schema: ZodType<T>,
): Promise<T> {
  const res = await http.patch(url, body);
  const parsed = schema.safeParse(res.data);
  if (!parsed.success) {
    throw new ApiError(
      `Unexpected response shape from ${url}`,
      "contract_mismatch",
      res.status,
      parsed.error.issues,
    );
  }
  return parsed.data;
}
