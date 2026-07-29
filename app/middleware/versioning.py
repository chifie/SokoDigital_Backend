"""API versioning middleware.

Adds ``X-API-Version`` and ``Sunset`` / ``Deprecation`` headers to responses
so that API clients can discover the current version and plan migrations
when a version is deprecated.

Usage in ``main.py``::

    from app.middleware.versioning import APIVersioningMiddleware

    app.add_middleware(APIVersioningMiddleware, latest_version=\"v1\")
"""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """Middleware that adds API versioning headers to every response.

    Headers added:
    - ``X-API-Version`` — The current API version (e.g. ``v1``).
    - ``X-API-Latest`` — The latest available version.
    - ``Deprecation`` — Set to ``true`` when the version is deprecated.
    - ``Sunset`` — RFC 8594 date when the version will be removed (only
      on deprecated versions).

    The version is inferred from the request URL path prefix (``/api/v1/…``,
    ``/api/v2/…``, etc.). If the path does not contain a version prefix,
    the ``latest_version`` is used.
    """

    def __init__(self, app: ASGIApp, latest_version: str = "v1") -> None:
        super().__init__(app)
        self.latest_version = latest_version

        # Track deprecated versions and their sunset dates (ISO 8601)
        self._deprecated: dict[str, str] = {
            # Example: "v1": "2027-01-01T00:00:00Z"  — uncomment when v2 ships
        }

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        response: Response = await call_next(request)

        # Infer version from the URL path
        version = self._detect_version(request)

        # Add version headers
        response.headers["X-API-Version"] = version
        response.headers["X-API-Latest"] = self.latest_version

        # Add deprecation warnings for old versions
        if version in self._deprecated:
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = self._deprecated[version]
            response.headers["Link"] = (
                f'<https://docs.sokodigital.com/api/{self.latest_version}>; '
                f'rel="successor-version"'
            )

        return response

    @staticmethod
    def _detect_version(request: Request) -> str:
        """Extract the API version from the URL path.

        Looks for a pattern like ``/api/v1/``, ``/api/v2/`` in the path.
        Falls back to the latest version if none is found.
        """
        import re

        match = re.search(r"/api/(v\d+)/", request.url.path)
        if match:
            return match.group(1)
        # Non-API routes (health, metrics, docs) — no version header needed
        return "latest"
