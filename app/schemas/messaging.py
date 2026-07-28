import uuid
from datetime import datetime

from pydantic import BaseModel


# ── Message ─────────────────────────────────────────────────────────────────
class MessageSend(BaseModel):
    conversation_id: uuid.UUID
    text: str
    attachments: list[str] | None = None


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    text: str
    attachments: list[str] | None = None
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Conversation ────────────────────────────────────────────────────────────
class ConversationCreate(BaseModel):
    participant_ids: list[uuid.UUID]
    product_id: uuid.UUID | None = None
    initial_message: str | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    participant_ids: list[uuid.UUID]
    product_id: uuid.UUID | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    """Conversation with messages included."""
    id: uuid.UUID
    participant_ids: list[uuid.UUID]
    product_id: uuid.UUID | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    messages: list[MessageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
