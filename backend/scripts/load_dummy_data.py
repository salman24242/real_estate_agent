"""Run the SQL migrations against the configured DATABASE_URL.

Usage (from the project root):

    python -m backend.scripts.load_dummy_data

It runs 001_initial.sql and 002_seed_data.sql in order. Safe to re-run; both
files use IF NOT EXISTS / ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

import asyncpg

from backend.config import settings


MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[1] / "db" / "migrations"


async def _run() -> None:
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    try:
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            print(f"[load_dummy_data] running {sql_file.name}...")
            sql = sql_file.read_text(encoding="utf-8")
            await conn.execute(sql)
        n = await conn.fetchval("SELECT COUNT(*) FROM listings")
        print(f"[load_dummy_data] done. {n} listings in DB.")
    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"[load_dummy_data] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
