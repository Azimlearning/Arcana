"""Error envelope + FastAPI exception handler (PRD §10.1).

Every known failure mode is an `ArcanaError` subclass. The HTTP layer
serialises them through `arcana_error_handler` into a consistent JSON
envelope: `{error, code, details, request_id}`. Unknown exceptions are
caught one layer up by FastAPI's default 500 handler.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ArcanaError(Exception):
    """Base for all known application errors."""

    code: str = "arcana_error"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class AllProvidersFailed(ArcanaError):
    """Every configured LLM provider failed — NFR-REL-02."""

    code = "all_providers_failed"
    http_status = 502


class RetrievalFailed(ArcanaError):
    """Hybrid retrieval could not produce evidence — FR-RET-04."""

    code = "retrieval_failed"
    http_status = 500


class IngestFailed(ArcanaError):
    """A document failed to ingest — FR-ING-08."""

    code = "ingest_failed"
    http_status = 422


class ValidationFailed(ArcanaError):
    """A block failed server-side validation — NFR-SEC-04 (fail closed)."""

    code = "validation_failed"
    http_status = 400


async def arcana_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI exception handler - register via `app.add_exception_handler`.

    Signature uses `Exception` to satisfy FastAPI's `ExceptionHandler`
    type contract; we narrow to `ArcanaError` inside (which it always
    will be at runtime since `add_exception_handler(ArcanaError, ...)`
    only routes `ArcanaError` subclasses here)."""
    if not isinstance(exc, ArcanaError):
        # Defensive: caller should only register us for ArcanaError, but if
        # we're invoked for a stray Exception, surface a clean 500.
        # `str(exc)` is logged for debugging but NOT echoed to the client —
        # provider tracebacks can contain paths, API keys, or internal hints
        # we don't want to leak (NFR-SEC-04 spirit).
        from api.core.logging import get_logger

        get_logger(__name__).error(
            "arcana.unhandled_exception",
            exc_type=type(exc).__name__,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal server error",
                "code": "internal_error",
                "details": {},
            },
        )
    payload: dict[str, Any] = {
        "error": exc.message,
        "code": exc.code,
        "details": exc.details,
    }
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=exc.http_status, content=payload)
