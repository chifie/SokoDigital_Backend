"""Webhook delivery service.

Dispatches events to registered webhook endpoints with retry logic
and delivery auditing.
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _sign_payload(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 sign the payload with the webhook secret."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def deliver_webhook(
    webhook_url: str,
    secret: str,
    event_type: str,
    payload: dict[str, Any],
    timeout: int = 10,
) -> dict[str, Any]:
    """Deliver an event to a single webhook endpoint.

    Returns a dict with: success, status_code, response_body, duration_ms, error_message.
    """
    body_bytes = json.dumps(payload, default=str).encode()
    signature = _sign_payload(body_bytes, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": event_type,
        "User-Agent": f"SokoDigital-Webhook/{settings.APP_VERSION}",
    }

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(webhook_url, content=body_bytes, headers=headers)
        duration_ms = int((time.monotonic() - start) * 1000)

        return {
            "success": resp.is_success,
            "status_code": resp.status_code,
            "response_body": resp.text[:5000],
            "duration_ms": duration_ms,
            "error_message": None if resp.is_success else f"HTTP {resp.status_code}",
        }
    except httpx.TimeoutException:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "status_code": None,
            "response_body": None,
            "duration_ms": duration_ms,
            "error_message": "Request timed out",
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "status_code": None,
            "response_body": None,
            "duration_ms": duration_ms,
            "error_message": str(exc),
        }
