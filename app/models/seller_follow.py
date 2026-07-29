import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SellerFollow(Base):
    __tablename__ = "seller_follows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # One follow per user per seller
    __table_args__ = (
        UniqueConstraint("seller_id", "user_id", name="uq_user_seller_follow"),
    )

    # Relationships
    seller: Mapped["Seller"] = relationship("Seller", backref="follow_relations", lazy="selectin")
    user: Mapped["User"] = relationship("User", backref="followed_sellers", lazy="selectin")

    def __repr__(self) -> str:
        return f"<SellerFollow {self.user_id} -> {self.seller_id}>"
