"""Deepgram REST clients for Speech-to-Text and Text-to-Speech.

Used by the browser-facing HTTP endpoints in `backend/routers/voice.py`.
The Twilio streaming path lives separately in `deepgram_stt.py`.
"""
from __future__ import annotations

import logging

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Deepgram endpoints
_STT_URL = "https://api.deepgram.com/v1/listen"
_TTS_URL = "https://api.deepgram.com/v1/speak"

# Models. `nova-3` is Deepgram's latest English STT model; `aura-asteria-en`
# is a natural-sounding English TTS voice in the Aura family.
_STT_MODEL = "nova-3"
_TTS_MODEL = "aura-asteria-en"

# A single shared async client gives us connection pooling + keepalive.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class DeepgramNotConfigured(RuntimeError):
    """Raised when the API key is missing / still placeholder."""


def _require_key() -> str:
    key = settings.DEEPGRAM_API_KEY
    if not key or key.startswith("REPLACE_ME"):
        raise DeepgramNotConfigured("DEEPGRAM_API_KEY is not configured")
    return key


async def transcribe(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """POST recorded audio to Deepgram and return the best transcript.

    `content_type` is forwarded as-is so Deepgram can auto-detect the codec
    (e.g. audio/webm;codecs=opus from a browser MediaRecorder).
    """
    api_key = _require_key()
    if not audio_bytes:
        return ""

    params = {"model": _STT_MODEL, "smart_format": "true", "punctuate": "true"}
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type or "application/octet-stream",
    }

    resp = await _get_client().post(
        _STT_URL, params=params, headers=headers, content=audio_bytes
    )
    resp.raise_for_status()
    data = resp.json()

    channels = (data.get("results") or {}).get("channels") or []
    if not channels:
        return ""
    alts = channels[0].get("alternatives") or []
    if not alts:
        return ""
    return (alts[0].get("transcript") or "").strip()


async def synthesize(text: str) -> bytes:
    """POST text to Deepgram Aura and return the generated audio (MP3)."""
    api_key = _require_key()
    trimmed = (text or "").strip()
    if not trimmed:
        return b""

    # Aura has a per-request character limit; keep requests reasonable.
    if len(trimmed) > 1800:
        trimmed = trimmed[:1800]

    params = {"model": _TTS_MODEL, "encoding": "mp3"}
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"text": trimmed}

    resp = await _get_client().post(
        _TTS_URL, params=params, headers=headers, json=payload
    )
    resp.raise_for_status()
    return resp.content
