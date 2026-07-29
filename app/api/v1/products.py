import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, require_admin
from app.config import settings
from app.database import get_db
from app.models.product import Product, ProductImage
from app.models.seller import Seller
from app.models.user import User
from app.schemas.common import Page
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


# ── GET /products (list with search/filter/sort + pagination) ───────────────
@router.get(
    "",
    response_model=Page[ProductResponse],
    summary="List products with search, filter, sort, and pagination",
    response_description="Paginated list of products with total count",
)
async def list_products(
    q: str | None = Query(None, description="Full-text search query"),
    category_id: uuid.UUID | None = Query(None, description="Filter by category ID"),
    seller_id: uuid.UUID | None = Query(None, description="Filter by seller ID"),
    min_price: float | None = Query(None, description="Minimum price filter", ge=0),
    max_price: float | None = Query(None, description="Maximum price filter", ge=0),
    condition: str | None = Query(None, description="Filter by condition (new, used, refurbished)"),
    status: str = Query("active", description="Filter by product status"),
    featured: bool | None = Query(None, description="Filter featured products only"),
    trending: bool | None = Query(None, description="Filter trending products only"),
    sort_by: str | None = Query(
        None, description="Sort field: created_at, price, rating, sold"
    ),
    sort_order: str = Query("desc", description="Sort direction: asc or desc"),
    skip: int = Query(0, ge=0, description="Number of records to skip (pagination)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Browse products with powerful search and filtering capabilities.

    Supports:
    - **Full-text search** across product names and descriptions
      (uses Meilisearch when configured, falls back to PostgreSQL ``tsvector``)
    - **Category, seller, price range, and condition** filters
    - **Sorting** by created_at, price, rating, or sales
    - **Featured/trending** product filters
    - **Cursor-less pagination** via skip/limit

    Returns a paginated response with ``items``, ``total``, ``skip``, ``limit``, and ``pages``.
    """
    # Try Meilisearch first when a search query is provided
    if q and settings.MEILISEARCH_URL:
        from app.services.search import search_products

        ms_filters: dict = {}
        if category_id:
            ms_filters["category_id"] = str(category_id)
        if seller_id:
            ms_filters["seller_id"] = str(seller_id)
        if min_price is not None:
            ms_filters["price"] = {"gte": min_price}
        if max_price is not None:
            ms_filters.setdefault("price", {})
            ms_filters["price"]["lte"] = max_price
        if condition:
            ms_filters["condition"] = condition
        if featured is not None:
            ms_filters["featured"] = featured
        if trending is not None:
            ms_filters["trending"] = trending
        ms_filters["status"] = status

        ms_sort = [f"{sort_by or 'created_at'}:{sort_order}"]

        ms_results = await search_products(
            query=q,
            filters=ms_filters if any(v is not None and v != {} for v in ms_filters.values()) else None,
            sort=ms_sort,
            limit=limit,
            offset=skip,
        )

        if ms_results is not None and ms_results["hits"]:
            product_ids = [h["id"] for h in ms_results["hits"]]
            if product_ids:
                ordering = case(
                    *[{Product.id: pid} for pid in product_ids],
                    else_=None,
                )
                result = await db.execute(
                    select(Product)
                    .options(selectinload(Product.images))
                    .where(Product.id.in_(product_ids))
                    .order_by(ordering)
                )
                items = result.scalars().unique().all()
                return Page(items=items, total=ms_results["total"], skip=skip, limit=limit)

    # Fallback: build the SQL query with filters
    filters = [Product.status == status]
    if q:
        search_vector = func.to_tsvector(
            "english", Product.name + " " + func.coalesce(Product.description, "")
        )
        search_query = func.to_tsquery("english", " & ".join(q.split()))
        filters.append(search_vector.op("@@")(search_query))
    if category_id:
        filters.append(Product.category_id == category_id)
    if seller_id:
        filters.append(Product.seller_id == seller_id)
    if min_price is not None:
        filters.append(Product.price >= min_price)
    if max_price is not None:
        filters.append(Product.price <= max_price)
    if condition:
        filters.append(Product.condition == condition)
    if featured is not None:
        filters.append(Product.featured == featured)
    if trending is not None:
        filters.append(Product.trending == trending)

    count_stmt = select(func.count(Product.id)).where(*filters)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(*filters)
    )

    if q:
        search_vector = func.to_tsvector(
            "english", Product.name + " " + func.coalesce(Product.description, "")
        )
        search_query = func.to_tsquery("english", " & ".join(q.split()))
        stmt = stmt.order_by(func.ts_rank(search_vector, search_query).desc())
    else:
        sort_column = {
            "created_at": Product.created_at,
            "price": Product.price,
            "rating": Product.rating,
            "sold": Product.sold,
        }.get(sort_by, Product.created_at)
        stmt = stmt.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().unique().all()

    return Page(items=items, total=total, skip=skip, limit=limit)


# ── GET /products/featured ──────────────────────────────────────────────────
@router.get(
    "/featured",
    response_model=list[ProductResponse],
    summary="List featured products",
    response_description="Collection of featured products sorted by rating",
)
async def list_featured_products(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of products to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve products marked as **featured**, ordered by rating descending.

    Useful for hero sections or promotional carousels on the homepage.
    """
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
    response_description="Collection of trending products sorted by sales",
)
async def list_trending_products(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of products to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve products marked as **trending**, ordered by units sold descending.

    Highlights best-selling products to drive conversions.
    """
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
    responses={404: {"description": "Product not found"}},
)
async def get_product_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch detailed information about a single product using its unique URL slug.

    Includes all product images, specifications, pricing, and seller info.
    """
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
    responses={
        201: {"description": "Product created successfully"},
        403: {"description": "Not a registered seller"},
        409: {"description": "Product slug already exists"},
    },
)
async def create_product(
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new product listing under the authenticated user's seller store.

    The authenticated user **must** be a registered seller first (see ``/sellers/onboard``).
    Product slugs must be unique across the entire marketplace.

    Images can be provided inline via the ``images`` array or uploaded separately
    via the ``/uploads`` endpoints.
    """
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
    responses={
        200: {"description": "Product updated successfully"},
        403: {"description": "Not authorized to update this product"},
        404: {"description": "Product not found"},
    },
)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing product listing.

    Only the **owning seller** or an **admin** can update a product.
    Partial updates are supported — only provided fields will be changed.
    """
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
    responses={
        204: {"description": "Product deleted successfully (no content)"},
        403: {"description": "Not authorized to delete this product"},
        404: {"description": "Product not found"},
    },
)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete a product listing and its associated images.

    Only the **owning seller** or an **admin** can delete a product.
    This action is irreversible.
    """
    product = await _get_product_or_404(db, product_id)
    seller = await _get_seller_for_user(db, current_user.id)

    if product.seller_id != seller.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own products",
        )

    await db.delete(product)
    await db.commit()
