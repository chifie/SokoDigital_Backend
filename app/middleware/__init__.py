"""Middleware package — shared utilities for middleware modules."""

from fastapi import Request
from starlette.routing import Match


def get_route_path(request: Request) -> str:
    """Extract the route template from a request.

    Returns the route pattern (e.g. ``/api/v1/products/{product_id}``)
    to avoid cardinality explosion in metrics and tracing labels.
    Falls back to the raw URL path if no route is matched.
    """
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return route.path
    return request.url.path
