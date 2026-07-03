"""Application error hierarchy and global HTTP error handling.

Rules:
- Domain/service code raises `AppError` subclasses — never `HTTPException`.
  (Keeps business logic transport-agnostic; SOLID dependency direction.)
- The handlers below translate errors into ONE stable JSON envelope:

    {"error": {"code": "not_found", "message": "...", "details": null}}

- Unexpected exceptions become opaque 500s: logged with stack trace
  server-side, never leaked to the client.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    """A requested resource does not exist."""

    status_code = 404
    code = "not_found"


class ConfigurationError(AppError):
    """The system is misconfigured; fail fast and loud."""

    status_code = 500
    code = "configuration_error"


class ExternalServiceError(AppError):
    """An upstream dependency (RPC, API, DB) failed or timed out."""

    status_code = 502
    code = "external_service_error"


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    """Build the single error envelope used by every error response."""
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the application."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        # Expected errors: client-safe message, warn-level log.
        logger.warning("%s: %s (path=%s)", exc.code, exc.message, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Unexpected errors: full trace server-side, opaque message client-side.
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "An internal error occurred."),
        )
