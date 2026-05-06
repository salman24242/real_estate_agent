"""Build parameterised SQL queries from a validated FilterState.

Security: SQL is never constructed from user strings. We only assemble a fixed set of
clauses with numbered placeholders ($1, $2, ...) and pass values as asyncpg parameters.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import asyncpg

from backend.agent.tag_vocabulary import validate_tags
from backend.db.listing_repo import _row_to_dict
from backend.models.filters import FilterState

logger = logging.getLogger(__name__)

ALLOWED_PROPERTY_TYPES: set[str] = {"apartment", "house", "studio", "villa", "penthouse", "townhouse"}
ALLOWED_LISTING_TYPES: set[str] = {"rent", "buy"}
MAX_PRICE_LIMIT: int = 100_000_000
MAX_RESULTS: int = 10


class FilterValidationError(Exception):
    """Raised when a filter value fails validation."""


def validate_filters(filters: FilterState) -> FilterState:
    """Validate and sanitise all filter values. Raises FilterValidationError on invalid input."""

    if not filters.city or not filters.city.strip():
        raise FilterValidationError("city is required")

    if filters.listing_type not in ALLOWED_LISTING_TYPES:
        raise FilterValidationError(f"Invalid listing_type: {filters.listing_type}")

    if filters.property_type and filters.property_type not in ALLOWED_PROPERTY_TYPES:
        raise FilterValidationError(f"Invalid property_type: {filters.property_type}")

    if filters.max_price is None or filters.max_price <= 0 or filters.max_price > MAX_PRICE_LIMIT:
        raise FilterValidationError(f"max_price out of allowed range: {filters.max_price}")

    if filters.min_price is not None and (filters.min_price < 0 or filters.min_price > MAX_PRICE_LIMIT):
        raise FilterValidationError(f"min_price out of allowed range: {filters.min_price}")

    if filters.min_price is not None and filters.max_price is not None and filters.min_price > filters.max_price:
        raise FilterValidationError("min_price cannot exceed max_price")

    if filters.bedrooms is not None and (filters.bedrooms < 0 or filters.bedrooms > 20):
        raise FilterValidationError(f"bedrooms out of range: {filters.bedrooms}")

    valid_must, invalid_must = validate_tags(filters.must_have_tags)
    valid_nice, invalid_nice = validate_tags(filters.nice_to_have_tags)

    if invalid_must or invalid_nice:
        logger.warning("Unknown tags dropped: must=%s nice=%s", invalid_must, invalid_nice)

    filters.must_have_tags = valid_must
    filters.nice_to_have_tags = valid_nice

    filters.city = filters.city.strip()

    return filters


async def execute_search(
    conn: asyncpg.Connection,
    filters: FilterState,
    broadened: bool = False,
) -> list[dict]:
    """Build and execute a parameterised query. Returns a list of listing dicts."""

    params: list[Any] = []
    clauses: list[str] = ["available = TRUE"]

    def add(clause_tmpl: str, value: Any) -> None:
        """Append a value and substitute '?' with the next $N placeholder."""
        params.append(value)
        clauses.append(clause_tmpl.replace("?", f"${len(params)}"))

    # Required filters (all verified by validate_filters)
    add("city ILIKE ?", f"%{filters.city}%")
    add("listing_type = ?", filters.listing_type)
    add("price <= ?", filters.max_price)

    # Optional filters
    if filters.min_price is not None:
        add("price >= ?", filters.min_price)

    if filters.bedrooms is not None:
        add("bedrooms >= ?", filters.bedrooms)

    if filters.property_type:
        add("property_type = ?", filters.property_type)

    if filters.must_have_tags:
        add("tags @> ?", filters.must_have_tags)

    if filters.description_keywords:
        # plainto_tsquery safely handles phrase input; we pass it as a parameter.
        keyword_str = " ".join(filters.description_keywords)
        add("search_vector @@ plainto_tsquery('english', ?)", keyword_str)

    # ORDER BY: rank by nice-to-have tag overlap, then price ascending.
    if filters.nice_to_have_tags:
        params.append(filters.nice_to_have_tags)
        order_by = (
            f"(SELECT COUNT(*) FROM unnest(tags) t "
            f"WHERE t = ANY(${len(params)})) DESC, price ASC"
        )
    else:
        order_by = "price ASC"

    where_clause = " AND ".join(clauses)
    params.append(MAX_RESULTS)
    limit_placeholder = f"${len(params)}"

    sql = f"""
        SELECT id, title, description, listing_type, property_type,
               price, bedrooms, bathrooms, area_sqft, city, neighbourhood,
               address, latitude, longitude, tags, images, agent_id, available, created_at
        FROM listings
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT {limit_placeholder}
    """

    logger.debug("Executing search (broadened=%s): %s params=%s", broadened, sql, params)
    rows = await conn.fetch(sql, *params)
    return [_row_to_dict(r) for r in rows]


async def execute_search_with_fallback(
    conn: asyncpg.Connection,
    filters: FilterState,
) -> tuple[list[dict], Optional[str]]:
    """Run the exact search; if empty, broaden progressively and report what was relaxed.

    Returns (results, broadening_note | None).
    """
    results = await execute_search(conn, filters)
    if results:
        return results, None

    broadened = filters.model_copy(deep=True)

    # Step 1: bump max_price by 20%
    if broadened.max_price:
        broadened.max_price = int(broadened.max_price * 1.2)
        results = await execute_search(conn, broadened, broadened=True)
        if results:
            return results, (
                f"No exact matches found. Showing results up to ${broadened.max_price:,} "
                "(20% above your budget)."
            )

    # Step 2: drop the last must-have tag
    if broadened.must_have_tags:
        dropped_tag = broadened.must_have_tags.pop()
        results = await execute_search(conn, broadened, broadened=True)
        if results:
            return results, (
                f"No exact matches found. Showing results without the "
                f"'{dropped_tag}' requirement."
            )

    # Step 3: drop bedrooms constraint
    if broadened.bedrooms is not None:
        broadened.bedrooms = None
        results = await execute_search(conn, broadened, broadened=True)
        if results:
            return results, "No exact matches found. Showing results with flexible bedroom count."

    return [], None
