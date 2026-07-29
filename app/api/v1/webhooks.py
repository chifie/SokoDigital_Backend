"""Webhook management API endpoints.

Allows users to register, list, update, delete webhook endpoints
and view delivery history.
"""

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.webhook import Webhook, WebhookEvent
from app.schemas.webhook import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookSecretResponse,
    WebhookTestResponse,
    WebhookUpdate,
)
from app.services.webhook import deliver_webhook

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.get(
    "",
    response_model=list[WebhookResponse],
    summary="List my webhook endpoints",
)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all webhook endpoints registered by the current user."""
    result = await db.execute(
        select(Webhook)
        .where(Webhook.user_id == current_user.id)
        .order_by(Webhook.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=WebhookSecretResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new webhook endpoint",
)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a new webhook URL that will receive event notifications.

    Returns the webhook secret **once** — store it securely. You'll need
    it to verify signatures on received payloads.
    """
    secret = secrets.token_hex(32)
    webhook = Webhook(
        user_id=current_user.id,
        url=str(body.url),
        secret=secret,
        events=body.events,
        description=body.description,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return WebhookSecretResponse(
        id=str(webhook.id),
        url=webhook.url,
        secret=secret,
        events=webhook.events,
        description=webhook.description,
    )


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook details",
)
async def get_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a specific webhook endpoint by ID."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == current_user.id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )
    return webhook


@router.put(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update a webhook endpoint",
)
async def update_webhook(
    webhook_id: uuid.UUID,
    body: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing webhook's URL, events, or active status."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == current_user.id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    if "url" in update_data:
        update_data["url"] = str(update_data["url"])

    for field, value in update_data.items():
        setattr(webhook, field, value)

    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook endpoint",
)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently remove a webhook endpoint and its delivery history."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == current_user.id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    await db.delete(webhook)
    await db.commit()


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Send a test ping to a webhook",
)
async def test_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a test event to verify the webhook endpoint is working."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == current_user.id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    result = await deliver_webhook(
        webhook_url=webhook.url,
        secret=webhook.secret,
        event_type="test.ping",
        payload={
            "event": "test.ping",
            "webhook_id": str(webhook.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Record the delivery attempt
    event = WebhookEvent(
        webhook_id=webhook.id,
        event_type="test.ping",
        payload={"event": "test.ping"},
        status_code=result["status_code"],
        response_body=result["response_body"],
        success=result["success"],
        duration_ms=result["duration_ms"],
        error_message=result["error_message"],
    )
    db.add(event)
    await db.commit()

    return WebhookTestResponse(
        success=result["success"],
        status_code=result["status_code"],
        duration_ms=result["duration_ms"],
        error_message=result["error_message"],
    )


@router.get(
    "/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
    summary="List webhook delivery history",
)
async def list_webhook_deliveries(
    webhook_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View the delivery history for a webhook endpoint."""
    # Verify ownership
    wh_result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == current_user.id,
        )
    )
    if wh_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    result = await db.execute(
        select(WebhookEvent)
        .where(WebhookEvent.webhook_id == webhook_id)
        .order_by(WebhookEvent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
