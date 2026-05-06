"""PostgreSQL connection pool management using asyncpg."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import asyncpg

from backend.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """Create the global connection pool. Called at app startup."""
    global _pool
    if _pool is not None:
        return _pool

    logger.info("Creating PostgreSQL connection pool...")
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=1,
        max_size=settings.DB_POOL_SIZE,
        command_timeout=30,
    )
    return _pool


async def close_db_pool() -> None:
    """Close the pool. Called at app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool has not been initialised yet")
    return _pool


async def get_db_conn() -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency — yields a connection from the pool."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_db_conn_context() -> AsyncIterator[asyncpg.Connection]:
    """Context-manager flavoured variant for non-route callers (e.g. WebSockets)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
