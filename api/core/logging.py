"""Structured JSON logging (NFR-MNT, PRD §10.1).

Single `configure_logging()` entry point, called once at app startup.
Every log line carries the request_id / agent / trace_id bound to the
current task via contextvars. PRD §11.6 names "request + agent trace ids"
as a structured-logging requirement; this module is that mechanism.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.stdlib import BoundLogger
from structlog.types import Processor

from api.core.settings import get_settings

_configured = False


def configure_logging() -> None:
    """Wire structlog + stdlib logging. Idempotent."""
    global _configured
    if _configured:
        return

    level = getattr(logging, get_settings().log_level)
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> BoundLogger:
    """Return a bound logger.

    Does NOT auto-configure — that would trigger `Settings()` at import
    time and break test collection when env vars aren't set. Call
    `configure_logging()` once from app startup (`main.py`).
    """
    return structlog.get_logger(name)


def bind_request_context(
    *,
    request_id: str,
    agent: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Bind per-turn context so every log line carries it."""
    extras: dict[str, str] = {"request_id": request_id}
    if agent:
        extras["agent"] = agent
    if trace_id:
        extras["trace_id"] = trace_id
    structlog.contextvars.bind_contextvars(**extras)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
