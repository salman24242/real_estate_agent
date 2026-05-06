"""Celery background tasks.

These are stubs you can flesh out when you wire up email delivery.
The orchestration shape is real: iterate saved_searches, re-run the filter,
diff against last_notified_ids, notify the user.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

import asyncpg

from backend.config import settings
from backend.db.query_builder import execute_search
from backend.models.filters import FilterState
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="check_saved_searches")
def check_saved_searches() -> dict:
    """Runs every 6 hours via Celery Beat."""
    return asyncio.run(_check_saved_searches_async())


async def _check_saved_searches_async() -> dict:
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT id, user_id, name, filters, last_notified_ids "
            "FROM saved_searches WHERE notify = TRUE"
        )
        total_new = 0
        for r in rows:
            filters_json = r["filters"] or {}
            try:
                filters = FilterState(**filters_json)
            except Exception:
                logger.warning("Skipping malformed saved search %s", r["id"])
                continue

            if not filters.city or not filters.listing_type or not filters.max_price:
                continue  # Incomplete filter, nothing to search.

            results = await execute_search(conn, filters)
            result_ids: set[uuid.UUID] = {uuid.UUID(r["id"]) for r in results}
            already: set[uuid.UUID] = set(r["last_notified_ids"] or [])
            new_ids = result_ids - already

            for lid in new_ids:
                send_listing_notification.delay(str(r["user_id"]), str(lid), r["name"] or "")

            if new_ids:
                merged = list(already | result_ids)
                await conn.execute(
                    "UPDATE saved_searches SET last_notified_ids = $1::uuid[], "
                    "last_checked_at = NOW() WHERE id = $2",
                    merged,
                    r["id"],
                )
                total_new += len(new_ids)
            else:
                await conn.execute(
                    "UPDATE saved_searches SET last_checked_at = NOW() WHERE id = $1",
                    r["id"],
                )
        return {"total_new_listings": total_new, "searches_checked": len(rows)}
    finally:
        await conn.close()


@celery_app.task(name="send_listing_notification")
def send_listing_notification(user_id: str, listing_id: str, search_name: str) -> None:
    """Stub. Hook up SendGrid / SES here."""
    logger.info(
        "Would notify user=%s about listing=%s (search=%r)",
        user_id, listing_id, search_name,
    )
