import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Array of participant UUIDs for efficient querying with @> operator
    participant_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID_TYPE(as_uuid=True)), nullable=False
    )
    # Optional product ID if the conversation is about a specific product
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Denormalized last message preview for list display
    last_message_preview: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    product: Mapped["Product"] = relationship("Product", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Conversation {self.id}>"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
    sender: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Message {self.id[:8]}...>"
