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


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Core info
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(
        String(500), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pricing
    price: Mapped[float] = mapped_column(Float, nullable=False)
    discount_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="TZS", nullable=False)

    # Brand & SKU
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    condition: Mapped[str] = mapped_column(
        String(50), default="new", nullable=False
    )

    # Inventory
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Foreign keys
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Flexible fields (stored as JSON)
    specifications: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    colors: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    sizes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True, index=True
    )
    delivery_options: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status & flags
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False, index=True
    )
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Ratings
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Policies
    warranty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    return_policy: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
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
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage",
        back_populates="product",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )
    category: Mapped["Category"] = relationship(
        "Category", backref="products", lazy="selectin"
    )
    seller: Mapped["Seller"] = relationship(
        "Seller", backref="products", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Product {self.slug}>"


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product", back_populates="images"
    )

    def __repr__(self) -> str:
        return f"<ProductImage {self.id}>"
