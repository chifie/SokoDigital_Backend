from datetime import datetime

from pydantic import BaseModel, EmailStr


# ── AI Chat ─────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """A single message in the conversation history."""

    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request payload for the AI chat endpoint."""

    message: str
    history: list[ChatMessage] | None = None


class ChatResponse(BaseModel):
    """Response from the AI assistant."""

    reply: str


# ── Newsletter ──────────────────────────────────────────────────────────────


class NewsletterSubscribeRequest(BaseModel):
    """Request to subscribe to the newsletter."""

    email: EmailStr


class NewsletterSubscriberResponse(BaseModel):
    """Public subscriber info returned after subscription."""

    id: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NewsletterUnsubscribeRequest(BaseModel):
    """Request to unsubscribe from the newsletter."""

    email: EmailStr
