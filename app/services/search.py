"""Meilisearch integration for full-text product search.

Provides a drop-in replacement for SQL-based full-text search with
typo tolerance, faceted filtering, and relevance ranking.
Falls back gracefully when Meilisearch is not configured.
"""

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded Meilisearch client (None when not configured)
_search_client: Any = None


def get_search_client() -> Any:
    """Get or create the Meilisearch client singleton."""
    global _search_client
    if _search_client is None and settings.MEILISEARCH_URL:
        try:
            import meilisearch

            _search_client = meilisearch.Client(
                settings.MEILISEARCH_URL,
                settings.MEILISEARCH_API_KEY or "",
            )
            logger.info("Meilisearch client initialized (url=%s)", settings.MEILISEARCH_URL)
        except ImportError:
            logger.warning("meilisearch not installed — search falls back to SQL")
        except Exception as exc:
            logger.error("Failed to connect to Meilisearch: %s", exc)
    return _search_client


async def index_product(product: dict[str, Any]) -> bool:
    """Index or update a product in Meilisearch."""
    client = get_search_client()
    if client is None:
        return False
    try:
        client.index("products").add_documents([product])
        return True
    except Exception as exc:
        logger.error("Failed to index product %s: %s", product.get("id"), exc)
        return False


async def remove_product(product_id: str) -> bool:
    """Remove a product from the Meilisearch index."""
    client = get_search_client()
    if client is None:
        return False
    try:
        client.index("products").delete_document(product_id)
        return True
    except Exception as exc:
        logger.error("Failed to remove product %s: %s", product_id, exc)
        return False


async def search_products(
    query: str,
    filters: dict[str, Any] | None = None,
    sort: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any] | None:
    """Search products using Meilisearch.

    Returns None if Meilisearch is not available (caller should fall back to SQL).
    Returns a dict with ``hits``, ``total``, ``query`` keys on success.
    """
    client = get_search_client()
    if client is None:
        return None

    try:
        search_params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if filters:
            search_params["filter"] = _build_filters(filters)
        if sort:
            search_params["sort"] = sort

        results = client.index("products").search(query, search_params)
        return {
            "hits": results.get("hits", []),
            "total": results.get("totalHits", 0),
            "query": query,
        }
    except Exception as exc:
        logger.error("Meilisearch search error: %s", exc)
        return None


async def configure_index() -> bool:
    """Configure the Meilisearch index settings (filterable/sortable attributes).

    Call once on startup if Meilisearch is configured.
    """
    client = get_search_client()
    if client is None:
        return False
    try:
        index = client.index("products")
        index.update_filterable_attributes(
            ["category_id", "seller_id", "status", "condition", "featured", "trending"]
        )
        index.update_sortable_attributes(["price", "created_at", "rating", "sold"])
        index.update_searchable_attributes(["name", "description", "brand", "tags"])
        logger.info("Meilisearch index configured successfully")
        return True
    except Exception as exc:
        logger.error("Failed to configure Meilisearch index: %s", exc)
        return False


def _build_filters(filters: dict[str, Any]) -> list[str]:
    """Convert a Python filter dict to Meilisearch filter expressions."""
    expressions = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, bool):
            expressions.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, str):
            expressions.append(f'{key} = "{value}"')
        elif isinstance(value, (int, float)):
            expressions.append(f"{key} = {value}")
        elif isinstance(value, (list, tuple)):
            parts = [f'{key} = "{v}"' if isinstance(v, str) else f"{key} = {v}" for v in value]
            expressions.append(f"({' OR '.join(parts)})")
        elif isinstance(value, dict):
            for op, val in value.items():
                if op == "gte":
                    expressions.append(f"{key} >= {val}")
                elif op == "lte":
                    expressions.append(f"{key} <= {val}")
                elif op == "gt":
                    expressions.append(f"{key} > {val}")
                elif op == "lt":
                    expressions.append(f"{key} < {val}")
    return expressions
