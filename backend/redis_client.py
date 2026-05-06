"""Redis-backed session store for conversation state."""
from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as redis

from backend.config import settings
from backend.models.session import SessionState

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """Lazy-init singleton Redis client."""
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _key(session_id: str) -> str:
    return f"session:{session_id}"


async def get_session(session_id: str) -> Optional[SessionState]:
    client = get_redis()
    raw = await client.get(_key(session_id))
    if raw is None:
        return None
    try:
        return SessionState.model_validate_json(raw)
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("Failed to parse session %s: %s", session_id, e)
        return None


async def save_session(session: SessionState) -> None:
    client = get_redis()
    await client.set(
        _key(session.session_id),
        session.model_dump_json(),
        ex=settings.SESSION_TTL_SECONDS,
    )


async def delete_session(session_id: str) -> None:
    client = get_redis()
    await client.delete(_key(session_id))
