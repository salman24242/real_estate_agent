"""All CRUD operations on the listings / saved_searches tables."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Optional

import asyncpg


LISTING_COLUMNS = """
    id, title, description, listing_type, property_type,
    price, bedrooms, bathrooms, area_sqft, city, neighbourhood,
    address, latitude, longitude, tags, images, agent_id, available, created_at
"""


def _row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    # asyncpg returns UUIDs and datetimes — make them JSON-friendly so that
    # dicts can be sent directly over websocket.send_json (which uses the
    # default encoder and does not know how to serialise these types).
    for k, v in list(d.items()):
        if isinstance(v, uuid.UUID):
            d[k] = str(v)
        elif isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
    if d.get("latitude") is not None:
        d["latitude"] = float(d["latitude"])
    if d.get("longitude") is not None:
        d["longitude"] = float(d["longitude"])
    return d


async def get_listing_by_id(conn: asyncpg.Connection, listing_id: str) -> Optional[dict]:
    try:
        listing_uuid = uuid.UUID(listing_id)
    except (TypeError, ValueError):
        return None
    row = await conn.fetchrow(
        f"SELECT {LISTING_COLUMNS} FROM listings WHERE id = $1",
        listing_uuid,
    )
    return _row_to_dict(row) if row else None


async def get_listings_by_ids(conn: asyncpg.Connection, listing_ids: list[str]) -> list[dict]:
    parsed: list[uuid.UUID] = []
    for lid in listing_ids:
        try:
            parsed.append(uuid.UUID(lid))
        except (TypeError, ValueError):
            continue
    if not parsed:
        return []
    rows = await conn.fetch(
        f"SELECT {LISTING_COLUMNS} FROM listings WHERE id = ANY($1::uuid[])",
        parsed,
    )
    return [_row_to_dict(r) for r in rows]


async def count_listings(conn: asyncpg.Connection) -> int:
    return await conn.fetchval("SELECT COUNT(*) FROM listings") or 0


async def save_user_search(
    conn: asyncpg.Connection,
    user_id: Optional[str],
    payload: dict,
) -> uuid.UUID:
    """Insert a new saved search and return its id."""
    if user_id is None:
        # Fall back to the demo user seeded in 002_seed_data.sql
        user_id = "99999999-9999-9999-9999-999999999999"

    new_id = await conn.fetchval(
        """
        INSERT INTO saved_searches (user_id, name, filters, notify)
        VALUES ($1, $2, $3::jsonb, $4)
        RETURNING id
        """,
        uuid.UUID(user_id),
        payload.get("name", "Unnamed search"),
        json.dumps(payload.get("filters", {})),
        bool(payload.get("notify", True)),
    )
    return new_id
