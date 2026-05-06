"""Skeleton Deepgram streaming STT connector.

Drop in your DEEPGRAM_API_KEY in .env, then wire `feed()` from the Twilio handler.
"""
from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable, Optional

import websockets

from backend.config import settings

logger = logging.getLogger(__name__)

DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=mulaw&sample_rate=8000&model=nova-2"
    "&language=en-US&endpointing=500&interim_results=false"
)


class DeepgramSTT:
    """Minimal async wrapper that streams PCM-mulaw chunks into Deepgram.

    on_transcript(text) is awaited every time Deepgram returns is_final=true.
    """

    def __init__(self, on_transcript: Callable[[str], Awaitable[None]]):
        self._on_transcript = on_transcript
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self) -> None:
        if settings.DEEPGRAM_API_KEY.startswith("REPLACE_ME"):
            raise RuntimeError("DEEPGRAM_API_KEY not configured")
        self._ws = await websockets.connect(
            DEEPGRAM_URL,
            extra_headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"},
        )

    async def feed(self, audio_chunk: bytes) -> None:
        """Push a raw audio chunk (mulaw 8kHz) into Deepgram."""
        if self._ws is None:
            await self.connect()
        assert self._ws is not None
        await self._ws.send(audio_chunk)

    async def listen(self) -> None:
        """Read transcripts off the Deepgram socket forever."""
        if self._ws is None:
            await self.connect()
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not msg.get("is_final"):
                    continue
                alt = (msg.get("channel") or {}).get("alternatives") or []
                if not alt:
                    continue
                transcript = (alt[0] or {}).get("transcript", "").strip()
                if transcript:
                    await self._on_transcript(transcript)
        except Exception as e:  # pragma: no cover
            logger.exception("Deepgram listen loop failed: %s", e)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
