"""HTTP + WebSocket endpoints for the chat agent."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.agent.orchestrator import process_message
from backend.database import get_db_conn, get_db_conn_context
from backend.models.session import SessionState
from backend.redis_client import delete_session, get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    listings: list[dict] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, conn=Depends(get_db_conn)) -> ChatResponse:
    """Single-turn HTTP chat. Creates a session if session_id is missing."""
    session_id = request.session_id or str(uuid.uuid4())
    session = await get_session(session_id) or SessionState(
        session_id=session_id, channel="chat"
    )

    reply, updated = await process_message(session, request.message, conn)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        listings=updated.last_results,
        filters=updated.filter_state.model_dump(),
    )


@router.delete("/chat/{session_id}")
async def reset_session(session_id: str) -> dict:
    await delete_session(session_id)
    return {"ok": True}


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str) -> None:
    """Multi-turn WebSocket chat.

    Client sends: {"message": "..."}
    Server sends: {"type": "reply", "content": "...", "session_id": "..."}
                  {"type": "listings", "data": [...]}
                  {"type": "error",    "message": "..."}
    """
    await websocket.accept()
    session = await get_session(session_id) or SessionState(
        session_id=session_id, channel="chat"
    )

    try:
        while True:
            data = await websocket.receive_json()
            user_message = (data or {}).get("message", "").strip()
            if not user_message:
                await websocket.send_json({"type": "error", "message": "empty message"})
                continue

            prev_results = session.last_results or []
            prev_ids = [r.get("id") for r in prev_results]

            async with get_db_conn_context() as conn:
                try:
                    reply, session = await process_message(session, user_message, conn)
                except Exception as e:  # pragma: no cover - defensive
                    logger.exception("WS chat error: %s", e)
                    await websocket.send_json(
                        {"type": "error", "message": "internal error, try again"}
                    )
                    continue

            await websocket.send_json(
                {"type": "reply", "content": reply, "session_id": session_id}
            )

            # Only broadcast listings when THIS turn actually produced/changed
            # results. Otherwise stale results from a previous search get
            # attached to unrelated replies like greetings or clarifications.
            new_results = session.last_results or []
            new_ids = [r.get("id") for r in new_results]
            # `process_message` assigns a fresh list when it performs a search.
            # This lets us distinguish "same search rerun" (should show photos
            # again) from non-search turns like greetings (must not resend stale
            # photos).
            results_refreshed_this_turn = session.last_results is not prev_results
            if new_results and (new_ids != prev_ids or results_refreshed_this_turn):
                await websocket.send_json(
                    {"type": "listings", "data": new_results}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
