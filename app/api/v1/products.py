import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.product import Product, ProductImage
from app.models.seller import Seller
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductImageSchema,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["Products"])


# ── Helper ──────────────────────────────────────────────────────────────────
async def _get_product_or_404(
    db: AsyncSession, product_id: uuid.UUID
) -> Product:
    """Fetch a product by ID or raise 404."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


async def _get_seller_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> Seller:
    """Fetch the seller profile for the current user or raise 403."""
    result = await db.execute(
        select(Seller).where(Seller.user_id == user_id)
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a registered seller to manage products",
        )
    return seller


# ── GET /products (list with search/filter/sort) ────────────────────────────
@router.get(
    "",
    response_model=list[ProductResponse],
    summary="List products with search, filter, and sort",
)
async def list_products(
    q: str | None = Query(None, description="Full-text search query"),
    category_id: uuid.UUID | None = None,
    seller_id: uuid.UUID | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    condition: str | None = None,
    status: str = Query("active", description="Filter by status"),
    featured: bool | None = None,
    trending: bool | None = None,
    sort_by: str | None = Query(
        None, description="created_at, price, rating, sold"
    ),
    sort_order: str = Query("desc", description="asc or desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List products with full-text search, filtering, and sorting."""
    stmt = select(Product).options(selectinload(Product.images))

    # Full-text search
    if q:
        search_vector = func.to_tsvector(
            "english", Product.name + " " + func.coalesce(Product.description, "")
        )
        search_query = func.to_tsquery("english", " & ".join(q.split()))
        stmt = stmt.where(search_vector.op("@@")(search_query))
        stmt = stmt.order_by(func.ts_rank(search_vector, search_query).desc())

    # Filters
    stmt = stmt.where(Product.status == status)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if seller_id:
        stmt = stmt.where(Product.seller_id == seller_id)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if condition:
        stmt = stmt.where(Product.condition == condition)
    if featured is not None:
        stmt = stmt.where(Product.featured == featured)
    if trending is not None:
        stmt = stmt.where(Product.trending == trending)

    # Sorting (apply default sort if not a search query)
    if not q:
        sort_column = {
            "created_at": Product.created_at,
            "price": Product.price,
            "rating": Product.rating,
            "sold": Product.sold,
        }.get(sort_by, Product.created_at)

        if sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().unique().all()


# ── GET /products/featured ──────────────────────────────────────────────────
@router.get(
    "/featured",
    response_model=list[ProductResponse],
    summary="List featured products",
)
async def list_featured_products(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return featured products, ordered by rating descending."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.featured == True, Product.status == "active")
        .order_by(Product.rating.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ── GET /products/trending ──────────────────────────────────────────────────
@router.get(
    "/trending",
    response_model=list[ProductResponse],
    summary="List trending products",
)
async def list_trending_products(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return trending products, ordered by sold count descending."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.trending == True, Product.status == "active")
        .order_by(Product.sold.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ── GET /products/{slug} ────────────────────────────────────────────────────
@router.get(
    "/{slug}",
    response_model=ProductResponse,
    summary="Get a product by its URL slug",
)
async def get_product_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single product by its URL slug."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.slug == slug)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


# ── POST /products (seller only) ────────────────────────────────────────────
@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product (seller only)",
)
async def create_product(
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new product under the authenticated seller's store."""
    seller = await _get_seller_for_user(db, current_user.id)

    # Check slug uniqueness
    existing = await db.execute(
        select(Product).where(Product.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this slug already exists",
        )

    # Create images first
    images_data = body.images
    body_dict = body.model_dump(exclude={"images"})
    body_dict["seller_id"] = seller.id

    product = Product(**body_dict)
    db.add(product)
    await db.flush()

    # Create product images
    for img_data in images_data:
        image = ProductImage(
            product_id=product.id,
            url=img_data.url,
            alt_text=img_data.alt_text,
            sort_order=img_data.sort_order,
        )
        db.add(image)

    # Update seller's product count
    seller.total_products = (
        await db.execute(
            select(func.count(Product.id)).where(Product.seller_id == seller.id)
        )
    ).scalar()

    await db.commit()
    await db.refresh(product)
    return product


# ── PUT /products/{product_id} (seller only) ────────────────────────────────
@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update a product (seller only)",
)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing product. Only the owning seller or admin can update."""
    product = await _get_product_or_404(db, product_id)
    seller = await _get_seller_for_user(db, current_user.id)

    if product.seller_id != seller.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own products",
        )

    # Check slug uniqueness if changing
    if body.slug is not None and body.slug != product.slug:
        existing = await db.execute(
            select(Product).where(Product.slug == body.slug)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this slug already exists",
            )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return product


# ── DELETE /products/{product_id} (seller only) ─────────────────────────────
@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product (seller only)",
)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a product. Only the owning seller or admin can delete."""
    product = await _get_product_or_404(db, product_id)
    seller = await _get_seller_for_user(db, current_user.id)

    if product.seller_id != seller.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own products",
        )

    await db.delete(product)
    await db.commit()
