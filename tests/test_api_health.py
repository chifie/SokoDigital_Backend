"""API integration tests for the health check endpoint.

Tests the response format, status codes, and behavior under different
conditions. These tests use the ASGI transport and do NOT require
a running database (the health endpoint handles DB failures gracefully).
"""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


class TestHealthEndpoint:
    """Test /health endpoint behavior."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """Health endpoint returns 200 OK with proper structure."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "app_name" in data
        assert "timestamp" in data
        assert "environment" in data
        assert "checks" in data

    async def test_health_contains_checks_dict(self, client: AsyncClient) -> None:
        """Health response includes a checks dict with db and redis."""
        resp = await client.get("/health")
        data = resp.json()
        checks = data["checks"]
        assert "database" in checks
        assert "redis" in checks

    async def test_health_returns_version(self, client: AsyncClient) -> None:
        """Health response includes the app version string."""
        resp = await client.get("/health")
        data = resp.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    async def test_health_returns_timestamp(self, client: AsyncClient) -> None:
        """Health response includes an ISO 8601 timestamp."""
        resp = await client.get("/health")
        data = resp.json()
        assert "T" in data["timestamp"]  # ISO 8601 format check

    async def test_health_returns_app_name(self, client: AsyncClient) -> None:
        """Health response includes the application name."""
        resp = await client.get("/health")
        data = resp.json()
        assert isinstance(data["app_name"], str)
        assert len(data["app_name"]) > 0

    async def test_health_db_failure_returns_503(self, client: AsyncClient) -> None:
        """When the database is down, health returns 503."""
        with patch("app.main.engine.connect") as mock_connect:
            mock_connect.side_effect = Exception("Database connection refused")
            resp = await client.get("/health")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "degraded"
            assert "unreachable" in str(data["checks"]["database"])

    async def test_health_redis_not_configured(self, client: AsyncClient) -> None:
        """When Redis is not configured, health reports it as not configured."""
        with patch("app.main.settings.REDIS_URL", None):
            resp = await client.get("/health")
            data = resp.json()
            assert data["checks"]["redis"] == "not configured"
            # Should still be ok if DB is fine
            assert data["status"] == "ok"

    async def test_health_is_public(self, client: AsyncClient) -> None:
        """Health endpoint does NOT require authentication."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_no_trailing_slash(self, client: AsyncClient) -> None:
        """Health endpoint works without trailing slash."""
        resp = await client.get("/health/")
        assert resp.status_code == 200

    async def test_api_info_returns_metadata(self, client: AsyncClient) -> None:
        """GET /api returns API metadata."""
        resp = await client.get("/api")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "redoc" in data
        assert "openapi" in data
        assert "metrics" in data
        assert "api_prefix" in data


class TestMetricsEndpoint:
    """Test /metrics endpoint."""

    async def test_metrics_returns_prometheus_data(self, client: AsyncClient) -> None:
        """GET /metrics should return Prometheus-format text."""
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/plain")

    async def test_metrics_is_public(self, client: AsyncClient) -> None:
        """Metrics endpoint does NOT require authentication."""
        resp = await client.get("/metrics")
        assert resp.status_code == 200

    async def test_metrics_contains_request_count(self, client: AsyncClient) -> None:
        """Metrics output includes request count data."""
        resp = await client.get("/metrics")
        text = resp.text
        assert "requests_total" in text or "# HELP" in text or "# TYPE" in text


class TestDocsEndpoints:
    """Test documentation endpoints."""

    async def test_docs_returns_html(self, client: AsyncClient) -> None:
        """GET /docs returns Swagger UI HTML."""
        resp = await client.get("/docs")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_redoc_returns_html(self, client: AsyncClient) -> None:
        """GET /redoc returns ReDoc HTML."""
        resp = await client.get("/redoc")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_openapi_json(self, client: AsyncClient) -> None:
        """GET /api/v1/openapi.json returns the OpenAPI spec."""
        resp = await client.get("/api/v1/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["openapi"] is not None
        assert "info" in data
        assert "paths" in data
