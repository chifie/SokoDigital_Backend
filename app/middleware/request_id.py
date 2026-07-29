"""Request ID middleware for request tracing and structured logging.

Every request gets a unique ``X-Request-ID`` header (either forwarded from
the client or auto-generated). This ID is injected into log messages for
correlation across services.
"""

import logging
import uuid
from collections.abc import Callable

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches a unique request ID to every request.

    - Reads ``X-Request-ID`` from the incoming request headers if present.
    - Otherwise generates a new ``uuid4`` hex string.
    - Sets the ``X-Request-ID`` header on the response.
    - Injects the ID into the request scope for use by route handlers.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)

        # Store in request state for route handlers
        request.state.request_id = request_id

        # Add to log context
        logger = logging.getLogger("app")
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = request_id
            return record

        logging.setLogRecordFactory(record_factory)

        # Process the request
        response: Response = await call_next(request)

        # Set the request ID header on the response
        response.headers["X-Request-ID"] = request_id
        return response


def setup_logging() -> None:
    """Configure structured logging with request ID support."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(request_id)-16s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set default request_id for logs outside request context
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return record

    logging.setLogRecordFactory(record_factory)
