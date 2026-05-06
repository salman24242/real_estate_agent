"""Voice endpoints.

Two flavours of voice are supported:

* Browser voice (HTTP): POST /voice/stt and POST /voice/tts, wired to
  Deepgram for both transcription and synthesis. Used by the mic button
  and audio playback in the React chat UI.
* Phone voice (WebSocket): /voice/ws/voice/{call_sid}, a Twilio Media
  Streams skeleton. Left in place for future use.
"""
from __future__ import annotations

import base64
import json
import logging

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.agent.deepgram_client import (
    DeepgramNotConfigured,
    synthesize as dg_synthesize,
    transcribe as dg_transcribe,
)
from backend.agent.orchestrator import process_message
from backend.config import settings
from backend.database import get_db_conn_context
from backend.models.session import SessionState
from backend.redis_client import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ---------------------------------------------------------------------------
# Browser voice (HTTP) - Deepgram STT + TTS
# ---------------------------------------------------------------------------
@router.post("/stt")
async def stt_endpoint(audio: UploadFile = File(...)) -> dict:
    """Transcribe a recorded audio blob (webm/opus, wav, mp3, ...) via Deepgram."""
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="empty audio")
        transcript = await dg_transcribe(
            audio_bytes, audio.content_type or "audio/webm"
        )
        return {"transcript": transcript}
    except DeepgramNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        logger.exception("Deepgram STT failed: %s", e.response.text[:500] if e.response else e)
        raise HTTPException(status_code=502, detail=f"STT upstream error ({e.response.status_code})")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


@router.post("/tts")
async def tts_endpoint(req: TTSRequest) -> Response:
    """Synthesise speech for `text` via Deepgram Aura; returns audio/mpeg."""
    try:
        audio_bytes = await dg_synthesize(req.text)
    except DeepgramNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        logger.exception("Deepgram TTS failed: %s", e.response.text[:500] if e.response else e)
        raise HTTPException(status_code=502, detail=f"TTS upstream error ({e.response.status_code})")
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="empty TTS response")
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.websocket("/ws/voice/{call_sid}")
async def voice_websocket(websocket: WebSocket, call_sid: str) -> None:
    """Skeleton Twilio Media Streams handler.

    Protocol:
      1. Twilio sends "start" with streamSid.
      2. Twilio sends "media" events with base64 mulaw 8kHz audio chunks.
         (Forward these to Deepgram — hook is marked below.)
      3. When a transcript finalises (dispatched internally with event="transcript"),
         we run it through the agent and stream TTS audio back.
      4. "stop" closes the call.
    """
    await websocket.accept()

    session_id = f"voice_{call_sid}"
    session = await get_session(session_id) or SessionState(
        session_id=session_id, channel="voice"
    )
    stream_sid: str | None = None

    try:
        async with get_db_conn_context() as conn:
            async for raw in websocket.iter_text():
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("event")

                if event_type == "start":
                    stream_sid = event.get("start", {}).get("streamSid")
                    logger.info("Voice stream started: %s", stream_sid)

                elif event_type == "media":
                    # TODO: forward event["media"]["payload"] to Deepgram.
                    # See backend/agent/deepgram_stt.py for the connector.
                    pass

                elif event_type == "transcript":
                    # Internal event: produced by the Deepgram handler when an
                    # utterance finalises.
                    transcript = event.get("transcript", "").strip()
                    if not transcript:
                        continue

                    reply, session = await process_message(session, transcript, conn)
                    audio_bytes = await _text_to_speech(reply)
                    if stream_sid and audio_bytes:
                        await _send_audio_to_twilio(websocket, stream_sid, audio_bytes)

                elif event_type == "stop":
                    logger.info("Voice stream stopped: %s", stream_sid)
                    break

    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected")


async def _text_to_speech(text: str) -> bytes:
    """Call ElevenLabs streaming TTS and return mulaw 8kHz audio bytes."""
    if settings.ELEVENLABS_API_KEY.startswith("REPLACE_ME"):
        logger.warning("ELEVENLABS_API_KEY not configured; skipping TTS")
        return b""

    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/"
        f"{settings.ELEVENLABS_VOICE_ID}/stream"
    )
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        "output_format": "ulaw_8000",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.content


async def _send_audio_to_twilio(
    websocket: WebSocket, stream_sid: str, audio_bytes: bytes
) -> None:
    """Frame mulaw bytes into 20ms Twilio chunks (640 bytes at 8kHz)."""
    chunk_size = 640
    for i in range(0, len(audio_bytes), chunk_size):
        chunk = audio_bytes[i : i + chunk_size]
        await websocket.send_json(
            {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": base64.b64encode(chunk).decode("utf-8")},
            }
        )
