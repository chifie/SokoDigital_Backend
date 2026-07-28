import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False  # "percentage" or "fixed"
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    min_purchase: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = unlimited
    current_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    applicable_categories: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
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

    def __repr__(self) -> str:
        return f"<Coupon {self.code}>"


class FlashSale(Base):
    __tablename__ = "flash_sales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount: Mapped[int] = mapped_column(Integer, nullable=False)  # percentage
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Many-to-many with products via JSON array of product IDs
    product_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )

    def __repr__(self) -> str:
        return f"<FlashSale {self.title}>"


class Banner(Base):
    __tablename__ = "banners"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta: Mapped[str | None] = mapped_column(String(255), nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    desktop_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    mobile_image: Mapped[str | None] = mapped_column(Text, nullable=True)

    badge: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    countdown_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    type: Mapped[str] = mapped_column(
        String(50), default="hero", nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    bg_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text_color: Mapped[str | None] = mapped_column(String(50), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_date: Mapped[datetime | None] = mapped_column(
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

    def __repr__(self) -> str:
        return f"<Banner {self.title}>"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False  # order, promotion, system, message, review
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", backref="notifications", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Notification {self.type}: {self.title}>"
