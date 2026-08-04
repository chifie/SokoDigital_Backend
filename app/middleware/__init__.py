"""Middleware package — shared utilities for middleware modules."""

from fastapi import Request
from starlette.routing import Match


def get_route_path(request: Request) -> str:
    """Extract the route template from a request.

    Returns the route pattern (e.g. ``/api/v1/products/{product_id}``)
    to avoid cardinality explosion in metrics and tracing labels.
    Falls back to the raw URL path if no route is matched.

    Handles FastAPI >= 0.140's lazy ``_IncludedRouter`` (which has no
    ``.path`` attribute) by expanding it into its effective candidate routes.
    """
    for route in request.app.routes:
        # FastAPI 0.140+ wraps included routers in a lazy _IncludedRouter
        # without a ``path`` — expand it to the real candidate routes.
        candidates = getattr(route, "effective_candidates", None)
        if candidates is not None:
            for candidate in candidates():
                path = getattr(candidate, "path", None)
                if path is None:
                    continue
                match, _ = candidate.matches(request.scope)
                if match == Match.FULL:
                    return path
            continue
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return route.path
    return request.url.path
