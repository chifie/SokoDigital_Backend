"""Request ID middleware for request tracing and structured logging.

Every request gets a unique ``X-Request-ID`` header (either forwarded from
the client or auto-generated). This ID is injected into log messages for
correlation across services.

Uses ``contextvars`` instead of modifying the global ``LogRecordFactory``
to ensure correctness in concurrent async requests.
"""

import logging
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

# Context variable that holds the current request ID.
# This is safe for concurrent async requests — each request gets its own
# context, so there are no race conditions.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the request ID for the current async context (if any)."""
    return _request_id_var.get()


class RequestIDFilter(logging.Filter):
    """Logging filter that injects ``request_id`` into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


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


def setup_logging() -> None:
    """Configure structured logging with request ID support.

    Adds a ``RequestIDFilter`` to the root logger so that every log record
    automatically carries the current request ID.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(request_id)-16s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(RequestIDFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove any pre-existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)
