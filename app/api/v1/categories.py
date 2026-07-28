import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryTreeNode,
    CategoryUpdate,
)

router = APIRouter(prefix="/categories", tags=["Categories"])


# ── Helper ──────────────────────────────────────────────────────────────────
async def _get_category_or_404(
    db: AsyncSession, category_id: uuid.UUID
) -> Category:
    """Fetch a category by ID or raise 404."""
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


# ── GET /categories (flat list) ─────────────────────────────────────────────
@router.get(
    "",
    response_model=list[CategoryResponse],
    summary="List all active categories (flat)",
)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = False,
):
    """Return all categories. Parent categories and subcategories
    are returned in a flat list. Use ``/categories/tree`` for a nested view.

    Pass ``?include_inactive=true`` to include inactive categories.
    """
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active == True)

    result = await db.execute(stmt)
    return result.scalars().all()


# ── GET /categories/tree (nested tree) ──────────────────────────────────────
@router.get(
    "/tree",
    response_model=list[CategoryTreeNode],
    summary="List all categories as a nested tree",
)
async def list_category_tree(
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = False,
):
    """Return all top-level categories with their children nested inside
    the ``children`` array. Ideal for navigation menus.
    """
    stmt = (
        select(Category)
        .options(selectinload(Category.children))
        .order_by(Category.sort_order, Category.name)
    )
    if not include_inactive:
        stmt = stmt.where(Category.is_active == True)

    result = await db.execute(stmt)
    categories = result.scalars().unique().all()

    # Only return top-level categories (no parent) — their children are loaded
    return [c for c in categories if c.parent_id is None]


# ── GET /categories/{slug} ──────────────────────────────────────────────────
@router.get(
    "/{slug}",
    response_model=CategoryTreeNode,
    summary="Get a single category by slug (with children)",
)
async def get_category_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single category by its URL slug, including its subcategories."""
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.slug == slug)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


# ── POST /categories (admin only) ───────────────────────────────────────────
@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category (admin only)",
)
async def create_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Create a new category. Requires authentication.

    The slug must be unique.
    """
    # Check slug uniqueness
    existing = await db.execute(
        select(Category).where(Category.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this slug already exists",
        )

    # Validate parent_id if provided
    if body.parent_id is not None:
        parent = await db.execute(
            select(Category).where(Category.id == body.parent_id)
        )
        if parent.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found",
            )

    category = Category(**body.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


# ── PUT /categories/{category_id} (admin only) ──────────────────────────────
@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update a category (admin only)",
)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Update an existing category. Requires authentication."""
    category = await _get_category_or_404(db, category_id)

    # Check slug uniqueness if slug is being changed
    if body.slug is not None and body.slug != category.slug:
        existing = await db.execute(
            select(Category).where(Category.slug == body.slug)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this slug already exists",
            )

    # Update only provided fields
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category


# ── DELETE /categories/{category_id} (admin only) ───────────────────────────
@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (admin only)",
)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Delete a category. Its subcategories will have ``parent_id`` set to NULL
    (``ON DELETE SET NULL``). Requires authentication.
    """
    category = await _get_category_or_404(db, category_id)
    await db.delete(category)
    await db.commit()
