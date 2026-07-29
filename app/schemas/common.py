from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response wrapper.

    Usage in a route handler (FastAPI):
    ```python
    from app.schemas.common import Page

    @router.get("", response_model=Page[ProductResponse])
    async def list_products(...):
        items, total = ...
        return Page(items=items, total=total, skip=skip, limit=limit)
    ```
    """

    items: list[T]
    total: int
    skip: int
    limit: int
    pages: int | None = None

    def model_post_init(self, __context) -> None:
        """Auto-calculate pages when total, limit, and skip are known."""
        if self.limit > 0:
            self.pages = (self.total + self.limit - 1) // self.limit
