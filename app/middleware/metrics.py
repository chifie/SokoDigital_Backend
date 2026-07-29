"""Prometheus metrics for the SokoDigital API.

Exposes:
- ``http_requests_total`` — Counter of requests by method, path, status
- ``http_request_duration_seconds`` — Histogram of request durations
- ``http_requests_in_progress`` — Gauge of currently in-flight requests

These are collected via middleware and served at ``/metrics``.

Usage in ``main.py``::

    from app.middleware.metrics import MetricsMiddleware, metrics_endpoint

    app.add_middleware(MetricsMiddleware)
    app.add_api_route(\"/metrics\", metrics_endpoint, include_in_schema=False)
"""

import time
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.middleware import get_route_path

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Stub classes for when prometheus_client is not installed
    class _StubMetric:  # pylint: disable=too-few-public-methods
        def labels(self, **kwargs: str) -> "_StubMetric":
            return self

        def inc(self, *args: object, **kwargs: object) -> None:
            pass

        def dec(self, *args: object, **kwargs: object) -> None:
            pass

        def observe(self, *args: object, **kwargs: object) -> None:
            pass

    Counter = _StubMetric  # type: ignore[misc,assignment]
    Histogram = _StubMetric  # type: ignore[misc,assignment]
    Gauge = _StubMetric  # type: ignore[misc,assignment]
    REGISTRY = None  # type: ignore[misc]


# ── Metric definitions ──────────────────────────────────────────────────────

REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total count of HTTP requests by method, path, and status code",
    labelnames=["method", "path", "status"],
)

REQUESTS_DURATION = Histogram(
    "http_request_duration_seconds",
    "Histogram of HTTP request durations in seconds",
    labelnames=["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Gauge of currently in-flight HTTP requests",
    labelnames=["method"],
)

EXCEPTIONS_TOTAL = Counter(
    "http_exceptions_total",
    "Total count of raised HTTPExceptions by status code",
    labelnames=["status"],
)


# ── Middleware ───────────────────────────────────────────────────────────────


class MetricsMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that collects Prometheus metrics on every request.

    Records request count, duration histogram, and in-progress gauge.
    The route template (e.g. ``/api/v1/products/{product_id}``) is used
    as the ``path`` label to avoid cardinality explosion.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        method = request.method

        # Derive a route template from the request's matched route
        path = self._get_route_path(request)
        response: Response | None = None

        REQUESTS_IN_PROGRESS.labels(method=method).inc()

        start = time.monotonic()
        try:
            response = await call_next(request)
            return response
        except Exception:
            EXCEPTIONS_TOTAL.labels(status="500").inc()
            raise
        finally:
            duration = time.monotonic() - start
            if response is not None:
                REQUESTS_TOTAL.labels(
                    method=method, path=path, status=str(response.status_code)
                ).inc()
                REQUESTS_DURATION.labels(method=method, path=path).observe(duration)
            REQUESTS_IN_PROGRESS.labels(method=method).dec()

    @staticmethod
    def _get_route_path(request: Request) -> str:
        """Extract the route template from the request, falling back to the URL path."""
        return get_route_path(request)


# ── Metrics endpoint ─────────────────────────────────────────────────────────


async def metrics_endpoint(request: Request) -> PlainTextResponse:
    """Serve Prometheus-format metrics at ``/metrics``."""
    if REGISTRY is None:
        return PlainTextResponse(
            "# prometheus_client not installed\n",
            media_type="text/plain; version=0.0.4",
        )
    return PlainTextResponse(
        generate_latest(REGISTRY).decode("utf-8"),
        media_type="text/plain; version=0.0.4",
    )
