from datetime import datetime
from typing import Any

from pydantic import BaseModel, HttpUrl


class WebhookCreate(BaseModel):
    """Register a new webhook endpoint."""

    url: HttpUrl
    events: list[str]
    description: str | None = None


class WebhookUpdate(BaseModel):
    """Update an existing webhook."""

    url: HttpUrl | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    description: str | None = None


class WebhookResponse(BaseModel):
    """Webhook endpoint details returned to clients."""

    id: str
    url: str
    events: list[str]
    is_active: bool
    description: str | None = None
    last_triggered_at: datetime | None = None
    failure_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookSecretResponse(BaseModel):
    """Response containing the webhook secret (shown once on creation)."""

    id: str
    url: str
    secret: str
    events: list[str]
    description: str | None = None


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery attempt record."""

    id: str
    event_type: str
    payload: dict[str, Any]
    status_code: int | None = None
    success: bool
    duration_ms: int | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookTestResponse(BaseModel):
    """Result of a webhook test ping."""

    success: bool
    status_code: int | None = None
    duration_ms: int | None = None
    error_message: str | None = None
