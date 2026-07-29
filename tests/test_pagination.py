"""Tests for the generic Page pagination schema."""

from app.schemas.common import Page
from app.schemas.product import ProductResponse


def test_page_auto_calculates_pages() -> None:
    """Page should auto-calculate the 'pages' field in model_post_init."""
    page = Page[int](items=[1, 2, 3], total=100, skip=0, limit=20)
    assert page.pages == 5  # 100 / 20 = 5


def test_page_partial_last_page() -> None:
    """Page should handle partial last page correctly."""
    page = Page[str](items=["a"], total=21, skip=20, limit=10)
    assert page.pages == 3  # ceil(21 / 10) = 3


def test_page_exact_divisible() -> None:
    """Page should handle exact divisible totals."""
    page = Page[int](items=[], total=30, skip=0, limit=10)
    assert page.pages == 3  # 30 / 10 = 3


def test_page_zero_items() -> None:
    """Page should handle zero total."""
    page = Page[int](items=[], total=0, skip=0, limit=20)
    assert page.pages == 0


def test_page_single_item() -> None:
    """Page should handle single item."""
    page = Page[int](items=[1], total=1, skip=0, limit=20)
    assert page.pages == 1


def test_page_with_product_response() -> None:
    """Page should work with Pydantic models as item type."""
    page = Page[ProductResponse](
        items=[],
        total=50,
        skip=0,
        limit=10,
    )
    assert page.pages == 5
    assert page.total == 50
    assert page.skip == 0
    assert page.limit == 10


def test_page_items_are_list() -> None:
    """Page items should be a list."""
    page = Page[int](items=[10, 20, 30], total=100, skip=0, limit=20)
    assert isinstance(page.items, list)
    assert len(page.items) == 3


def test_page_zero_limit_no_division_by_zero() -> None:
    """Page should handle zero limit gracefully (avoids division by zero)."""
    page = Page[int](items=[], total=100, skip=0, limit=0)
    # pages should remain None since we skip calculation for limit=0
    assert page.pages is None
