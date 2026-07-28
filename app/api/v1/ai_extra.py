import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models.newsletter import NewsletterSubscriber
from app.models.user import User
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    NewsletterSubscribeRequest,
    NewsletterSubscriberResponse,
    NewsletterUnsubscribeRequest,
)
from app.services.ai import chat_with_ai
from app.services.email import send_email

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI & Extras"])


# ═══════════════════════════════════════════════════════════════════════════
# AI Chat
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/ai/chat",
    response_model=ChatResponse,
    summary="Chat with the AI shopping assistant",
)
async def ai_chat(
    body: ChatRequest,
    current_user: User | None = Depends(get_current_user),
):
    """Send a message to the AI shopping assistant and get a reply.

    The optional ``history`` field carries previous messages so the AI
    maintains context. Authentication is optional — unauthenticated users
    can still chat, but the assistant won't know their account details.
    """
    history_list = None
    if body.history:
        history_list = [m.model_dump() for m in body.history]

    try:
        reply = await chat_with_ai(body.message, history_list)
    except Exception as exc:
        logger.error("AI chat error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service is temporarily unavailable. Please try again later.",
        )

    return ChatResponse(reply=reply)


# ═══════════════════════════════════════════════════════════════════════════
# Newsletter
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/newsletter/subscribe",
    response_model=NewsletterSubscriberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to the newsletter",
)
async def subscribe_newsletter(
    body: NewsletterSubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Subscribe an email address to the marketplace newsletter.

    If the email is already subscribed (active or inactive), it is
    re-activated.
    """
    result = await db.execute(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.email == body.email
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already subscribed",
            )
        # Re-activate
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        subscriber = existing
    else:
        subscriber = NewsletterSubscriber(email=body.email)
        db.add(subscriber)
        await db.commit()
        await db.refresh(subscriber)

    # Send welcome email (fire-and-forget, don't block the response)
    try:
        await send_email(
            to_email=body.email,
            template_name="newsletter_welcome",
            context={
                "unsubscribe_url": f"{settings.APP_URL or '#'}/newsletter/unsubscribe?email={body.email}",
            },
        )
    except Exception:
        logger.warning("Failed to send welcome email to %s", body.email)

    return subscriber


@router.post(
    "/newsletter/unsubscribe",
    summary="Unsubscribe from the newsletter",
)
async def unsubscribe_newsletter(
    body: NewsletterUnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Unsubscribe an email from the newsletter."""
    result = await db.execute(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.email == body.email,
            NewsletterSubscriber.is_active == True,
        )
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscriber not found or already unsubscribed",
        )

    subscriber.is_active = False
    await db.commit()
    return {"message": "Successfully unsubscribed"}


@router.get(
    "/newsletter/subscribers",
    response_model=list[NewsletterSubscriberResponse],
    summary="List all active newsletter subscribers (admin)",
)
async def list_subscribers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active newsletter subscribers. Requires admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    result = await db.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.is_active == True)
        .order_by(NewsletterSubscriber.created_at.desc())
    )
    return result.scalars().all()
