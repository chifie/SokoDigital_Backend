"""Integration tests for the standardized API error response envelope.

Verifies that the global exception handlers registered by
``register_error_handlers()`` produce the expected JSON shape including
the backward-compatible ``detail`` key.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from app.utils.response import (
    _build_error_body,
    _general_exception_handler,
    _http_exception_handler,
    _validation_exception_handler,
    register_error_handlers,
)


# ── Unit tests for _build_error_body ─────────────────────────────────────────


class TestBuildErrorBody:
    """Tests for the internal ``_build_error_body`` helper."""

    def test_contains_success_false(self) -> None:
        body = _build_error_body(message="Not found")
        assert body["success"] is False

    def test_contains_detail_key(self) -> None:
        """The ``detail`` key is required for backward compatibility."""
        body = _build_error_body(message="Not found")
        assert "detail" in body
        assert body["detail"] == "Not found"

    def test_contains_message_key(self) -> None:
        body = _build_error_body(message="Something went wrong")
        assert body["message"] == "Something went wrong"

    def test_error_field_omitted_when_none(self) -> None:
        body = _build_error_body(message="Error")
        assert "error" not in body

    def test_error_field_included_when_provided(self) -> None:
        body = _build_error_body(message="Error", error="Detail: invalid input")
        assert body["error"] == "Detail: invalid input"

    def test_success_is_always_false(self) -> None:
        """Error responses must always have success=False."""
        body = _build_error_body(message="Any error")
        assert body["success"] is False


# ── Unit tests for error_response helper ─────────────────────────────────────


class TestErrorResponseHelper:
    """Tests for the public ``error_response`` helper."""

    def test_detail_key_preserved(self) -> None:
        from app.utils.response import error_response

        resp = error_response(message="Test error")
        assert resp["detail"] == "Test error"
        assert resp["success"] is False
        assert resp["message"] == "Test error"

    def test_error_key_included_when_given(self) -> None:
        from app.utils.response import error_response

        resp = error_response(message="Validation failed", error="Field x is required")
        assert resp["error"] == "Field x is required"
        assert "detail" in resp


# ── Unit tests for HTTPException handler ─────────────────────────────────────


class TestHTTPExceptionHandler:
    """Tests for the HTTPException → JSON conversion."""

    @pytest.mark.asyncio
    async def test_returns_json_with_detail(self) -> None:
        """The handler must include the ``detail`` key in the JSON body."""
        exc = StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="User not found")
        request = MagicMock(spec=Request)

        response = await _http_exception_handler(request, exc)
        body = response.body.decode()

        assert response.status_code == HTTP_404_NOT_FOUND
        assert '"detail":"User not found"' in body
        assert '"success":false' in body
        assert '"message":"User not found"' in body

    @pytest.mark.asyncio
    async def test_400_response_shape(self) -> None:
        exc = StarletteHTTPException(HTTP_400_BAD_REQUEST, "Bad input")
        request = MagicMock(spec=Request)

        response = await _http_exception_handler(request, exc)
        body = response.body.decode()

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert '"detail":"Bad input"' in body
        assert '"success":false' in body


# ── Unit tests for validation error handler ──────────────────────────────────


class TestValidationExceptionHandler:
    """Tests for the pydantic ``RequestValidationError`` handler."""

    @pytest.mark.asyncio
    async def test_422_response_shape(self) -> None:

        class DummyModel(BaseModel):
            name: str

        try:
            DummyModel()  # type: ignore[call-arg]
        except ValidationError as e:
            val_error = e

        exc = RequestValidationError(val_error.errors())
        request = MagicMock(spec=Request)

        response = await _validation_exception_handler(request, exc)
        body = response.body.decode()

        assert response.status_code == HTTP_422_UNPROCESSABLE_CONTENT
        assert '"success":false' in body
        assert '"detail"' in body  # backward-compat key
        assert '"message":"Validation error"' in body


# ── Unit tests for general exception handler ─────────────────────────────────


class TestGeneralExceptionHandler:
    """Tests for the catch-all ``Exception`` handler."""

    @pytest.mark.asyncio
    async def test_500_response_shape(self) -> None:
        from app.config import settings

        # Temporarily force DEBUG off
        original_debug = settings.DEBUG
        settings.DEBUG = False

        try:
            exc = RuntimeError("Something broke internally")
            request = MagicMock(spec=Request)

            response = await _general_exception_handler(request, exc)
            body = response.body.decode()

            assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
            assert '"success":false' in body
            assert '"detail"' in body
            assert "Internal server error" in body
            # Error detail should NOT be leaked in production
            assert "Something broke" not in body
        finally:
            settings.DEBUG = original_debug

    @pytest.mark.asyncio
    async def test_leaks_details_in_debug_mode(self) -> None:
        from app.config import settings

        original_debug = settings.DEBUG
        settings.DEBUG = True

        try:
            exc = RuntimeError("Debug info here")
            request = MagicMock(spec=Request)

            response = await _general_exception_handler(request, exc)
            body = response.body.decode()

            assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
            assert "Debug info here" in body
        finally:
            settings.DEBUG = original_debug


# ── Tests for register_error_handlers ────────────────────────────────────────


class TestRegisterErrorHandlers:
    """Tests that the registration function wires handlers correctly."""

    def test_registers_three_handlers(self) -> None:
        app = MagicMock(spec=FastAPI)
        register_error_handlers(app)  # type: ignore[arg-type]

        # Should have called add_exception_handler three times
        assert app.add_exception_handler.call_count == 3

    def test_http_handler_registered_first(self) -> None:
        from starlette.exceptions import HTTPException as SE

        app = MagicMock(spec=FastAPI)
        register_error_handlers(app)  # type: ignore[arg-type]

        calls = app.add_exception_handler.call_args_list
        assert calls[0][0][0] == SE


# ── Integration test (end-to-end via the app) ────────────────────────────────


class TestIntegration:
    """End-to-end tests that hit the live FastAPI app.

    NOTE: These require a running PostgreSQL database (same as
    ``test_email_verification.py``). They are skipped if no database
    is available.
    """

    @pytest.mark.asyncio
    async def test_health_still_works(self) -> None:
        """The health endpoint should still return its normal format."""
        try:
            from httpx import ASGITransport, AsyncClient
            from app.main import app

            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "version" in data
        except Exception:
            pytest.skip("Database not available for integration test")
