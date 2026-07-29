"""Standardized API response wrapper and exception handlers.

Provides a consistent JSON envelope for all API responses and a global
exception handler that converts unhandled ``HTTPException`` and ``ValidationError``
errors into the same envelope format.
"""

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

T = TypeVar("T")


# ── Envelope model ───────────────────────────────────────────────────────────


class APIResponse(BaseModel, Generic[T]):
    """Standard API response envelope.

    Every response from the API is wrapped in this envelope, giving
    clients a predictable structure to parse.
    """

    success: bool
    message: str
    data: T | None = None
    error: str | None = None


def success_response(
    data: T | None = None,
    message: str = "Success",
) -> dict[str, Any]:
    """Build a success response dict."""
    return APIResponse(success=True, message=message, data=data).model_dump(
        exclude_none=True
    )


def error_response(
    message: str = "An error occurred",
    error: str | None = None,
) -> dict[str, Any]:
    """Build an error response dict."""
    return APIResponse(
        success=False, message=message, error=error
    ).model_dump(exclude_none=True)


# ── Exception handlers ───────────────────────────────────────────────────────


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Catch HTTPException and return a consistent JSON envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=str(exc.detail),
        ),
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Catch pydantic validation errors and return a clean JSON envelope."""
    errors = exc.errors()
    detail = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'][1:] if loc != 'body')}: {e['msg']}"
        for e in errors
    )
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            message="Validation error",
            error=detail,
        ),
    )


async def _general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch any unhandled exception and return a 500 envelope."""
    # In production, don't leak the internal error details
    detail = str(exc) if __debug__ else "Internal server error"
    return JSONResponse(
        status_code=500,
        content=error_response(
            message="Internal server error",
            error=detail,
        ),
    )


# ── Registrar ────────────────────────────────────────────────────────────────


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on a FastAPI application."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _general_exception_handler)
