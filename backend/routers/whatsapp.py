"""WhatsApp webhook endpoint (Twilio-backed).

Incoming WhatsApp messages arrive here as form-encoded POSTs from Twilio.
We map the sender's phone number to a Redis session, run the same agent
loop used by the web chat, then push replies back via the Twilio REST API
(including one image-with-caption per matching listing).

Voice notes are transcribed via Deepgram STT, and every agent reply is also
sent as an audio voice note via Deepgram TTS — mirroring the web app's voice
experience.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid as _uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient

from backend.agent.deepgram_client import synthesize, transcribe
from backend.agent.orchestrator import process_message
from backend.config import settings
from backend.database import get_db_conn_context
from backend.models.session import SessionState
from backend.redis_client import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response/>'
_MAX_REPLY_CHARS = 1500
_MAX_LISTINGS_PER_REPLY = 3

# ---------------------------------------------------------------------------
# In-memory audio cache for TTS files served to Twilio
# ---------------------------------------------------------------------------
_AUDIO_CACHE: dict[str, tuple[bytes, float]] = {}
_AUDIO_TTL_SECS = 300  # 5 minutes


def _cache_audio(audio_bytes: bytes) -> str:
    """Store audio and return a unique ID to retrieve it."""
    _evict_stale_audio()
    audio_id = _uuid.uuid4().hex
    _AUDIO_CACHE[audio_id] = (audio_bytes, time.time())
    return audio_id


def _evict_stale_audio() -> None:
    cutoff = time.time() - _AUDIO_TTL_SECS
    stale = [k for k, (_, ts) in _AUDIO_CACHE.items() if ts < cutoff]
    for k in stale:
        _AUDIO_CACHE.pop(k, None)


def _twilio_is_configured() -> bool:
    return (
        bool(settings.TWILIO_ACCOUNT_SID)
        and not settings.TWILIO_ACCOUNT_SID.startswith("REPLACE_ME")
        and bool(settings.TWILIO_AUTH_TOKEN)
        and not settings.TWILIO_AUTH_TOKEN.startswith("REPLACE_ME")
    )


def _twilio_client() -> TwilioClient:
    if not _twilio_is_configured():
        raise RuntimeError("Twilio is not configured; set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
    return TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def _session_id_for(from_number: str) -> str:
    """Turn 'whatsapp:+15551234567' into a stable session key."""
    digits = re.sub(r"\D", "", from_number or "")
    return f"whatsapp_{digits or 'anonymous'}"


def _normalise_markdown_for_whatsapp(text: str) -> str:
    """WhatsApp uses *bold* not **bold**; normalise what the LLM produces.

    Also collapses any accidental triple-emphasis and strips markdown
    headings, which WhatsApp doesn't render.
    """
    if not text:
        return ""
    # **bold** -> *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Remove leading "# ", "## ", "### " on lines (markdown headings)
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    return text


async def _verify_twilio_signature(request: Request, form: dict[str, str]) -> bool:
    """Return True iff the X-Twilio-Signature header is valid for this request.

    Returns True in dev mode (no auth token configured) so the endpoint can
    be exercised locally without Twilio in the loop. In production the token
    MUST be set, making validation strictly enforced.
    """
    if not _twilio_is_configured():
        logger.warning("Twilio auth token not set - skipping signature check (dev mode)")
        return True

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False

    # When the app sits behind a proxy (ngrok, load balancer) the scheme or
    # host may be rewritten; use the forwarded headers if present.
    proto = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if proto and host:
        url = f"{proto}://{host}{request.url.path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
    else:
        url = str(request.url)

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    return validator.validate(url, form, signature)


def _build_listing_caption(listing: dict[str, Any]) -> str:
    price = listing.get("price")
    price_str = f"${int(price):,}" if isinstance(price, (int, float)) else "Price on request"
    title = listing.get("title") or "Property"
    bed = listing.get("bedrooms", "?")
    bath = listing.get("bathrooms", "?")
    sqft = listing.get("area_sqft", "?")
    location = listing.get("neighbourhood") or listing.get("city") or ""
    parts = [
        f"*{price_str}* — {title}",
        f"{bed} bd · {bath} ba · {sqft} sqft",
    ]
    if location:
        parts.append(location)
    return "\n".join(parts)


async def _send_twilio_message(
    client: TwilioClient,
    from_sender: str,
    to: str,
    body: str,
    media_url: Optional[list[str]] = None,
) -> None:
    """Send one WhatsApp message via Twilio REST in a thread (SDK is sync)."""
    def _send() -> None:
        kwargs: dict[str, Any] = {"from_": from_sender, "to": to, "body": body}
        if media_url:
            kwargs["media_url"] = media_url
        client.messages.create(**kwargs)

    try:
        await asyncio.to_thread(_send)
    except TwilioRestException as e:
        logger.error("Twilio send failed (code=%s): %s", e.code, e.msg)


async def _download_twilio_media(media_url: str) -> bytes:
    """Download a media file from Twilio (requires HTTP basic auth)."""
    import httpx

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            media_url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content


def _derive_base_url(request: Request) -> str:
    """Get the public base URL from the incoming request headers.

    When behind ngrok the forwarded headers tell us the real public URL.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}"


async def _process_and_reply(
    from_number: str,
    body: str,
    session_id: str,
    base_url: str,
) -> None:
    """Run the agent for one user turn and push replies back to WhatsApp."""
    try:
        session = await get_session(session_id) or SessionState(
            session_id=session_id, channel="whatsapp"
        )
        if session.channel != "whatsapp":
            session.channel = "whatsapp"

        async with get_db_conn_context() as conn:
            reply, session = await process_message(session, body, conn)
    except Exception:
        logger.exception("Agent failed for %s; sending fallback", session_id)
        reply = "Sorry, something went wrong on my end. Please try again in a moment."
        session = None  # type: ignore[assignment]

    if not _twilio_is_configured():
        logger.warning("Twilio not configured; agent reply not delivered: %s", reply[:80])
        return

    client = _twilio_client()
    from_sender = settings.TWILIO_PHONE_NUMBER
    if not from_sender:
        logger.error("TWILIO_PHONE_NUMBER not set; cannot send replies")
        return

    # 1) Text reply (always).
    reply_clean = _normalise_markdown_for_whatsapp(reply).strip()
    if len(reply_clean) > _MAX_REPLY_CHARS:
        reply_clean = reply_clean[: _MAX_REPLY_CHARS - 3] + "..."
    if reply_clean:
        await _send_twilio_message(client, from_sender, from_number, reply_clean)

    # 2) One image-with-caption per matching listing (only when a search ran).
    listings = (getattr(session, "last_results", None) or []) if session else []
    for listing in listings[:_MAX_LISTINGS_PER_REPLY]:
        images = listing.get("images") or []
        image_url = images[0] if images else None
        caption = _build_listing_caption(listing)
        await _send_twilio_message(
            client,
            from_sender,
            from_number,
            caption,
            media_url=[image_url] if image_url else None,
        )

    # 3) Voice reply via TTS (mirrors the web app's voice experience).
    if reply_clean:
        try:
            audio_bytes = await synthesize(reply_clean)
            if audio_bytes:
                audio_id = _cache_audio(audio_bytes)
                audio_url = f"{base_url}/whatsapp/audio/{audio_id}.mp3"
                await _send_twilio_message(
                    client,
                    from_sender,
                    from_number,
                    "",  # empty body — audio speaks for itself
                    media_url=[audio_url],
                )
        except Exception:
            logger.warning("TTS for WhatsApp reply failed; text was still sent", exc_info=True)


@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> Response:
    """Twilio -> us. Acknowledge fast, do real work in the background."""
    form = await request.form()
    form_dict = {k: str(v) for k, v in form.items()}

    if not await _verify_twilio_signature(request, form_dict):
        logger.warning("Rejected webhook with invalid Twilio signature")
        raise HTTPException(status_code=403, detail="invalid signature")

    from_number = form_dict.get("From", "").strip()
    body = (form_dict.get("Body") or "").strip()
    num_media = int(form_dict.get("NumMedia", "0") or 0)
    base_url = _derive_base_url(request)

    if not from_number:
        return Response(content=_EMPTY_TWIML, media_type="application/xml")

    # If a voice note (or other audio) was sent, transcribe it via Deepgram.
    if not body and num_media > 0:
        media_type = form_dict.get("MediaContentType0", "")
        media_url = form_dict.get("MediaUrl0", "")
        if media_type.startswith("audio/") and media_url:
            session_id = _session_id_for(from_number)
            logger.info("WhatsApp voice note from %s — downloading & transcribing", session_id)
            asyncio.create_task(
                _handle_voice_note(from_number, media_url, media_type, session_id, base_url)
            )
            return Response(content=_EMPTY_TWIML, media_type="application/xml")

        # Non-audio media (images, documents) — ask for text.
        if _twilio_is_configured() and settings.TWILIO_PHONE_NUMBER:
            asyncio.create_task(
                _send_twilio_message(
                    _twilio_client(),
                    settings.TWILIO_PHONE_NUMBER,
                    from_number,
                    "I can only read text and voice messages right now. What are you looking for?",
                )
            )
        return Response(content=_EMPTY_TWIML, media_type="application/xml")

    if not body:
        return Response(content=_EMPTY_TWIML, media_type="application/xml")

    session_id = _session_id_for(from_number)
    logger.info("WhatsApp in: %s -> %s", session_id, body[:80])

    asyncio.create_task(_process_and_reply(from_number, body, session_id, base_url))

    return Response(content=_EMPTY_TWIML, media_type="application/xml")


async def _handle_voice_note(
    from_number: str,
    media_url: str,
    content_type: str,
    session_id: str,
    base_url: str,
) -> None:
    """Download a WhatsApp voice note, transcribe it, and run the agent."""
    try:
        audio_bytes = await _download_twilio_media(media_url)
        transcript = await transcribe(audio_bytes, content_type)
    except Exception:
        logger.exception("Voice note transcription failed for %s", session_id)
        if _twilio_is_configured() and settings.TWILIO_PHONE_NUMBER:
            await _send_twilio_message(
                _twilio_client(),
                settings.TWILIO_PHONE_NUMBER,
                from_number,
                "Sorry, I couldn't understand your voice message. Could you type it instead?",
            )
        return

    if not transcript:
        if _twilio_is_configured() and settings.TWILIO_PHONE_NUMBER:
            await _send_twilio_message(
                _twilio_client(),
                settings.TWILIO_PHONE_NUMBER,
                from_number,
                "I couldn't catch what you said. Could you try again or type your message?",
            )
        return

    logger.info("WhatsApp voice transcribed: %s -> %s", session_id, transcript[:80])
    await _process_and_reply(from_number, transcript, session_id, base_url)


@router.get("/audio/{audio_id}.mp3")
async def serve_audio(audio_id: str) -> Response:
    """Serve a cached TTS audio file so Twilio can fetch it as media."""
    entry = _AUDIO_CACHE.get(audio_id)
    if not entry:
        raise HTTPException(status_code=404, detail="audio not found or expired")
    audio_bytes, _ = entry
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.get("/health")
async def whatsapp_health() -> dict:
    """Sanity endpoint you can hit from the browser."""
    return {
        "ok": True,
        "twilio_configured": _twilio_is_configured(),
        "from_number": settings.TWILIO_PHONE_NUMBER or None,
    }
