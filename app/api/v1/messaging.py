import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.messaging import Conversation, Message
from app.models.user import User
from app.schemas.messaging import (
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
    MessageResponse,
    MessageSend,
)

router = APIRouter(prefix="/conversations", tags=["Messaging"])


# ── Helper ──────────────────────────────────────────────────────────────────
async def _get_conversation_or_404(
    db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages).selectinload(Message.sender))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user_id not in conv.participant_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")
    return conv


# ── GET /conversations ──────────────────────────────────────────────────────
@router.get("", response_model=list[ConversationResponse], summary="List my conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all conversations the current user is a participant in."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.participant_ids.any(current_user.id))
        .order_by(desc(Conversation.last_message_at), desc(Conversation.created_at))
    )
    return result.scalars().all()


# ── POST /conversations ─────────────────────────────────────────────────────
@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED, summary="Start a new conversation")
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new conversation and optionally send the first message."""
    # Ensure current user is included as a participant
    all_participants = list(set(body.participant_ids) | {current_user.id})

    # Check existing conversation with same participants and product
    existing = await db.execute(
        select(Conversation).where(
            Conversation.participant_ids.any(current_user.id),
        )
    )
    for conv in existing.scalars().all():
        existing_set = set(conv.participant_ids) if conv.participant_ids else set()
        if existing_set == set(all_participants) and conv.product_id == body.product_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conversation already exists with these participants",
            )

    conv = Conversation(
        participant_ids=all_participants,
        product_id=body.product_id,
    )

    if body.initial_message:
        conv.last_message_preview = body.initial_message[:500]
        conv.last_message_at = datetime.now(timezone.utc)

    db.add(conv)
    await db.flush()

    if body.initial_message:
        msg = Message(
            conversation_id=conv.id,
            sender_id=current_user.id,
            text=body.initial_message,
        )
        db.add(msg)

    await db.commit()
    await db.refresh(conv)
    return conv


# ── GET /conversations/unread/count ─────────────────────────────────────────
@router.get("/unread/count", summary="Get unread message count across all conversations")
async def unread_message_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Count messages that are unread and not sent by the current user."""
    result = await db.execute(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.participant_ids.any(current_user.id),
            Message.read == False,
            Message.sender_id != current_user.id,
        )
    )
    return {"unread_count": result.scalar() or 0}


# ── GET /conversations/{conversation_id} ────────────────────────────────────
@router.get("/{conversation_id}", response_model=ConversationDetail, summary="Get conversation with messages")
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a conversation with all its messages."""
    return await _get_conversation_or_404(db, conversation_id, current_user.id)


# ── POST /conversations/{conversation_id}/messages ──────────────────────────
@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED, summary="Send a message")
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageSend,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message in an existing conversation."""
    conv = await _get_conversation_or_404(db, conversation_id, current_user.id)

    msg = Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        text=body.text,
        attachments=body.attachments,
    )
    db.add(msg)

    # Update conversation preview
    conv.last_message_preview = body.text[:500]
    conv.last_message_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(msg)
    return msg


# ── GET /conversations/{conversation_id}/messages (polling) ─────────────────
@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="Get messages (supports polling via ?since=timestamp)",
)
async def get_messages(
    conversation_id: uuid.UUID,
    since: datetime | None = Query(None, description="Only return messages after this timestamp"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get messages for a conversation. Supports polling by passing
    ``?since=ISO_TIMESTAMP`` to only get new messages after a given time.
    """
    conv = await _get_conversation_or_404(db, conversation_id, current_user.id)

    stmt = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    if since:
        stmt = stmt.where(Message.created_at > since)

    result = await db.execute(stmt)
    messages = result.scalars().all()

    # Mark messages as read for the current user
    for msg in messages:
        if msg.sender_id != current_user.id and not msg.read:
            msg.read = True
    await db.commit()

    return messages


# ── GET /conversations/unread/count ─────────────────────────────────────────
@router.get("/unread/count", summary="Get unread message count across all conversations")
async def unread_message_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Count messages that are unread and not sent by the current user."""
    result = await db.execute(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.participant_ids.any(current_user.id),
            Message.read == False,
            Message.sender_id != current_user.id,
        )
    )
    return {"unread_count": result.scalar() or 0}
