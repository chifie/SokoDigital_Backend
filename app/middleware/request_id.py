"""Request ID middleware for request tracing and structured logging.

Every request gets a unique ``X-Request-ID`` header (either forwarded from
the client or auto-generated). This ID is injected into log messages for
correlation across services.

Uses ``contextvars`` instead of modifying the global ``LogRecordFactory``
to ensure correctness in concurrent async requests.

Supports **two logging modes**:
- Plain-text (default via ``logging``)
- Structured JSON (via ``structlog`` when ``STRUCTLOG_ENABLED=true``)
"""

import json
import logging
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings

# Context variable that holds the current request ID.
# This is safe for concurrent async requests — each request gets its own
# context, so there are no race conditions.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the request ID for the current async context (if any)."""
    return _request_id_var.get()


# ── Plain-text logging filter (backward compatible) ──────────────────────────


class RequestIDFilter(logging.Filter):
    """Logging filter that injects ``request_id`` into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


# ── Structured JSON logging via structlog ────────────────────────────────────


class JSONLogFormatter(logging.Formatter):
    """Custom formatter that outputs log records as newline-delimited JSON.

    Produces output compatible with log shipping tools (Elasticsearch,
    Datadog, Splunk, etc.). Includes request_id from the async context.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, default=str)


# ── Middleware ───────────────────────────────────────────────────────────────


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches a unique request ID to every request.

    - Reads ``X-Request-ID`` from the incoming request headers if present.
    - Otherwise generates a new ``uuid4`` hex string.
    - Sets the ``X-Request-ID`` header on the response.
    - Injects the ID into the async context so log records carry it.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)

        # Store in the async context (safe for concurrent requests)
        token = _request_id_var.set(request_id)

        # Store in request state for route handlers
        request.state.request_id = request_id

        try:
            response: Response = await call_next(request)
            # Set the request ID header on the response
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Restore the previous context value (cleanup)
            _request_id_var.reset(token)


# ── Logging setup ────────────────────────────────────────────────────────────


def setup_logging() -> None:
    """Configure structured logging.

    If ``settings.ENVIRONMENT`` is ``production`` or ``STRUCTLOG_ENABLED``
    env var is set, uses JSON output via ``JSONLogFormatter``. Otherwise
    uses plain-text output with request_id support.
    """
    use_json = settings.ENVIRONMENT == "production" or bool(
        __import__("os").environ.get("STRUCTLOG_ENABLED", "")
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove any pre-existing handlers to avoid duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler()

    if use_json:
        handler.setFormatter(JSONLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(request_id)-16s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.addFilter(RequestIDFilter())

    root.addHandler(handler)
