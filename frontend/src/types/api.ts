/**
 * Shared API types mirroring the FastAPI backend contracts.
 *
 * These match backend/models/schemas. Endpoint-specific response types live
 * with their service in src/lib/api/* (added in Milestone 2). Keep this file
 * for cross-cutting shapes only.
 */

/** The backend's single error envelope: {"error": {code, message, details}}. */
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

/** Component/overall health status vocabulary (backend HealthReport). */
export type HealthStatus = "ok" | "degraded" | "down";
