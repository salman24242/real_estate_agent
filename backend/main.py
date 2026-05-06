"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agent.deepgram_client import close_client as close_deepgram_client
from backend.config import settings
from backend.database import close_db_pool, get_db_conn_context, init_db_pool
from backend.db.listing_repo import count_listings
from backend.redis_client import close_redis, get_redis
from backend.routers.chat import router as chat_router
from backend.routers.voice import router as voice_router
from backend.routers.whatsapp import router as whatsapp_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting up: initialising DB pool and Redis...")
    await init_db_pool()
    # Smoke-test Redis
    try:
        await get_redis().ping()
        logger.info("Redis connection OK")
    except Exception as e:  # pragma: no cover
        logger.warning("Redis not reachable: %s", e)

    try:
        async with get_db_conn_context() as conn:
            n = await count_listings(conn)
            logger.info("Database OK: %d listings loaded", n)
    except Exception as e:  # pragma: no cover
        logger.warning("Database not reachable yet: %s", e)

    yield

    logger.info("Shutting down: closing DB, Redis, and HTTP clients...")
    await close_db_pool()
    await close_redis()
    await close_deepgram_client()


app = FastAPI(
    title="Real Estate Chat Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(whatsapp_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict:
    return {
        "name": "Real Estate Chat Agent",
        "version": "1.0.0",
        "endpoints": {
            "chat_http": "POST /api/chat",
            "chat_ws": "WS /api/ws/chat/{session_id}",
            "voice_ws": "WS /voice/ws/voice/{call_sid}",
            "whatsapp_webhook": "POST /whatsapp/webhook",
            "health": "GET /health",
        },
    }
