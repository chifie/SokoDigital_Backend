"""OpenTelemetry tracing middleware for distributed tracing.

Automatically creates spans for every HTTP request, capturing method,
path, status code, and duration. Spans can be exported to Jaeger,
Datadog, or any OpenTelemetry-compatible backend.

Requires ``opentelemetry-api`` and ``opentelemetry-sdk`` packages.

Usage in ``main.py``::

    from app.middleware.tracing import setup_tracing, TracingMiddleware

    setup_tracing(service_name=\"sokodigital-api\")
    app.add_middleware(TracingMiddleware)
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.middleware import get_route_path

logger = logging.getLogger(__name__)

# ── Lazy import of OpenTelemetry ─────────────────────────────────────────────
# This keeps the app functional when opentelemetry is not installed.

_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    # Stub classes for when OpenTelemetry is not installed
    class _NoopTracer:
        def start_as_current_span(self, name: str, **kwargs: object) -> object:
            return _NoopSpan()

        def start_span(self, name: str, **kwargs: object) -> object:
            return _NoopSpan()

    class _NoopSpan:
        def __enter__(self) -> _NoopSpan:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def set_attribute(self, key: str, value: object) -> None:
            pass

        def record_exception(self, exc: Exception) -> None:
            pass

        def set_status(self, status: object) -> None:
            pass

    class _NoopStatusCode:
        OK = 0
        ERROR = 1

    trace = type("_NoopTrace", (), {  # type: ignore[assignment]
        "get_tracer": lambda name: _NoopTracer(),
        "Status": type("Status", (), {"__init__": lambda self, code: None}),
        "StatusCode": _NoopStatusCode,
    })()


# ── Setup ────────────────────────────────────────────────────────────────────


TRACER_NAME = "sokodigital-api"


def setup_tracing(service_name: str = "sokodigital-api") -> None:
    """Initialize the OpenTelemetry tracer provider.

    Exports spans via OTLP over HTTP. The exporter endpoint is read from
    the ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var (default: ``http://localhost:4318``).

    If ``opentelemetry`` packages are not installed, this function is a no-op.
    """
    if not _OTEL_AVAILABLE:
        logger.info(
            "OpenTelemetry not installed — tracing disabled. "
            "Install: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-http"
        )
        return

    otel_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4318",
    )

    resource = Resource.create(
        attributes={
            "service.name": service_name,
            "service.version": settings.APP_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{otel_endpoint}/v1/traces")
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    logger.info("OpenTelemetry tracing initialized (exporting to %s)", otel_endpoint)


def get_tracer() -> object:
    """Return the tracer instance for manual instrumentation."""
    return trace.get_tracer(TRACER_NAME)


# ── Middleware ───────────────────────────────────────────────────────────────


class TracingMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that creates an OpenTelemetry span per request.

    The span captures:
    - ``http.method`` — HTTP method (GET, POST, ...)
    - ``http.route`` — Route template (e.g. ``/api/v1/products/{product_id}``)
    - ``http.url`` — Full request URL
    - ``http.status_code`` — Response status code
    - ``http.duration_ms`` — Request duration in milliseconds

    On unhandled exceptions, the span is recorded as an error before
    the exception propagates.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._tracer = trace.get_tracer(TRACER_NAME)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        method = request.method
        path = request.url.path
        route_path = self._get_route_path(request)

        span_name = f"{method} {route_path}"

        with self._tracer.start_as_current_span(
            span_name,
            kind=trace.SpanKind.SERVER,
        ) as span:  # type: ignore[attr-defined]
            span.set_attribute("http.method", method)  # type: ignore[attr-defined]
            span.set_attribute("http.route", route_path)  # type: ignore[attr-defined]
            span.set_attribute("http.url", str(request.url))  # type: ignore[attr-defined]

            start = time.monotonic()
            try:
                response: Response = await call_next(request)
                duration_ms = (time.monotonic() - start) * 1000
                span.set_attribute("http.status_code", response.status_code)  # type: ignore[attr-defined]
                span.set_attribute("http.duration_ms", round(duration_ms, 2))  # type: ignore[attr-defined]
                return response
            except Exception as exc:
                duration_ms = (time.monotonic() - start) * 1000
                span.record_exception(exc)  # type: ignore[attr-defined]
                span.set_attribute("http.duration_ms", round(duration_ms, 2))  # type: ignore[attr-defined]
                span.set_status(trace.Status(trace.StatusCode.ERROR))  # type: ignore[attr-defined]
                raise

    @staticmethod
    def _get_route_path(request: Request) -> str:
        """Extract the route template from the request."""
        return get_route_path(request)
