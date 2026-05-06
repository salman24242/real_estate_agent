"""Application configuration loaded from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Grok / xAI (OpenAI-compatible API)
    GROK_API_KEY: str = "REPLACE_ME_WITH_YOUR_GROK_API_KEY"
    GROK_BASE_URL: str = "https://api.x.ai/v1"
    GROK_MODEL: str = "grok-2-latest"

    # PostgreSQL
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/realestate"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_TTL_SECONDS: int = 3600

    # App
    SECRET_KEY: str = "change-me"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Twilio (voice)
    TWILIO_ACCOUNT_SID: str = "REPLACE_ME_WITH_YOUR_TWILIO_ACCOUNT_SID"
    TWILIO_AUTH_TOKEN: str = "REPLACE_ME_WITH_YOUR_TWILIO_AUTH_TOKEN"
    TWILIO_PHONE_NUMBER: str = "REPLACE_ME_WITH_YOUR_TWILIO_PHONE_NUMBER"

    # Deepgram (STT)
    DEEPGRAM_API_KEY: str = "REPLACE_ME_WITH_YOUR_DEEPGRAM_API_KEY"

    # ElevenLabs (TTS)
    ELEVENLABS_API_KEY: str = "REPLACE_ME_WITH_YOUR_ELEVENLABS_API_KEY"
    ELEVENLABS_VOICE_ID: str = "REPLACE_ME_WITH_YOUR_ELEVENLABS_VOICE_ID"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
