"""Main agent orchestrator.

Flow:
    user message
      -> append to session
      -> call Grok with CLARIFICATION system prompt (JSON-only reply)
      -> if not ready and turns < max: return follow-up question
      -> else: build + validate FilterState, query DB, call Grok with SYNTHESIS prompt
      -> persist session, return reply
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import asyncpg
from openai import AsyncOpenAI

from backend.agent.prompts import (
    CLARIFICATION_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT_CHAT,
    SYNTHESIS_SYSTEM_PROMPT_VOICE,
    SYNTHESIS_SYSTEM_PROMPT_WHATSAPP,
)
from backend.config import settings
from backend.db.listing_repo import (
    get_listing_by_id,
    get_listings_by_ids,
    save_user_search,
)
from backend.db.query_builder import (
    FilterValidationError,
    execute_search_with_fallback,
    validate_filters,
)
from backend.models.filters import FilterState
from backend.models.session import Message, SessionState
from backend.redis_client import save_session

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_TURNS = 4

# Grok exposes an OpenAI-compatible API, so we use the OpenAI SDK.
_client = AsyncOpenAI(
    api_key=settings.GROK_API_KEY,
    base_url=settings.GROK_BASE_URL,
)


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------
async def process_message(
    session: SessionState,
    user_message: str,
    db_conn: asyncpg.Connection,
) -> tuple[str, SessionState]:
    """Process one user turn and return (reply_text, updated_session)."""

    session.messages.append(Message(role="user", content=user_message))
    session.turn_count += 1

    # ---- Deterministic greeting short-circuit --------------------------------
    # If the user's message is just a greeting ("hi", "hello", "hey", ...) we
    # reply with a warm greeting directly. This avoids the case where a stale
    # session in Redis (same session_id across page reloads) makes the LLM
    # treat the greeting as a continuation and respond with a dry clarifier.
    if _is_pure_greeting(user_message):
        reply = _greeting_reply()
        session.messages.append(Message(role="assistant", content=reply))
        await save_session(session)
        return reply, session

    # ---- Deterministic conversation-closer short-circuit ---------------------
    # If the user is closing the conversation ("no thanks", "that's all",
    # "bye", "i'm good", ...) we reply with a warm sign-off instead of
    # re-running the previous search with leftover filters in the history.
    if _is_conversation_closer(user_message):
        reply = _closer_reply(session)
        session.messages.append(Message(role="assistant", content=reply))
        await save_session(session)
        return reply, session

    # ---- Clarification / extraction call --------------------------------------
    try:
        clarification = await _call_clarification(session)
    except Exception as e:
        logger.exception("Clarification call failed: %s", e)
        reply = (
            "I'm having trouble reaching the assistant right now. "
            "Could you try again in a moment?"
        )
        session.messages.append(Message(role="assistant", content=reply))
        await save_session(session)
        return reply, session

    # Safety-net regex extraction from the user's latest message. We merge it
    # into the LLM's clarification so that even if the model fails to extract
    # (or returns a useless generic follow-up), we still know what the user
    # said and can respond contextually.
    regex_extracted = _regex_extract(user_message)
    _merge_extraction(clarification, regex_extracted)

    ready = bool(clarification.get("ready_to_query"))
    missing_required = _missing_required_fields(clarification)

    # Defensive: if the model says "ready" but didn't actually give us the
    # three required fields, treat it as still-clarifying so we don't surface
    # the stern validator error on a greeting / chit-chat turn.
    if ready and missing_required:
        ready = False

    # ---- Not ready: ask follow-up --------------------------------------------
    if not ready and session.turn_count < MAX_CLARIFICATION_TURNS:
        # If we have any extracted fields, always build a context-aware
        # follow-up ourselves - the LLM's generic follow_up_question often
        # ignores what the user just said.
        has_any_extraction = bool(
            clarification.get("city")
            or clarification.get("listing_type")
            or clarification.get("property_type")
        )
        if has_any_extraction:
            follow_up = _targeted_follow_up(clarification, missing_required)
        else:
            follow_up = (
                clarification.get("follow_up_question")
                or _targeted_follow_up(clarification, missing_required)
                or _default_opener(session)
            )
        session.messages.append(Message(role="assistant", content=follow_up))
        await save_session(session)
        return follow_up, session

    # ---- Ready (or hit turn cap): build filters + query ----------------------
    filters = _extract_filters(clarification)

    try:
        filters = validate_filters(filters)
    except FilterValidationError as e:
        logger.info("Filter validation failed: %s", e)
        # Second-line defence: if validation fails (e.g. we hit the turn cap
        # but still don't have max_price), ask for what's missing rather than
        # surfacing a stern error or ignoring what the user said.
        missing_required = _missing_required_fields(clarification)
        reply = _targeted_follow_up(clarification, missing_required) or _default_opener(session)
        session.messages.append(Message(role="assistant", content=reply))
        await save_session(session)
        return reply, session

    session.filter_state = filters

    results, broadening_note = await execute_search_with_fallback(db_conn, filters)

    # ---- Synthesise response --------------------------------------------------
    if session.channel == "voice":
        synthesis_prompt = SYNTHESIS_SYSTEM_PROMPT_VOICE
    elif session.channel == "whatsapp":
        synthesis_prompt = SYNTHESIS_SYSTEM_PROMPT_WHATSAPP
    else:
        synthesis_prompt = SYNTHESIS_SYSTEM_PROMPT_CHAT

    try:
        reply = await _call_synthesis(session, results, broadening_note, synthesis_prompt)
    except Exception as e:
        logger.exception("Synthesis call failed: %s", e)
        reply = _fallback_synthesis(results, broadening_note)

    session.messages.append(Message(role="assistant", content=reply))
    session.last_results = results
    session.ready_to_query = True
    await save_session(session)

    return reply, session


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
async def _call_clarification(session: SessionState) -> dict:
    """Ask Grok to either ask a follow-up question or emit extracted filters as JSON."""
    messages = [{"role": "system", "content": CLARIFICATION_SYSTEM_PROMPT}]
    for m in session.messages:
        # Grok/OpenAI only accepts roles {system, user, assistant, tool}.
        role = m.role if m.role in {"user", "assistant", "system"} else "user"
        messages.append({"role": role, "content": m.content})

    response = await _client.chat.completions.create(
        model=settings.GROK_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=600,
        response_format={"type": "json_object"},
    )

    text = (response.choices[0].message.content or "").strip()
    text = _strip_fences(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse clarification JSON: %r", text)
        return {
            "ready_to_query": False,
            "follow_up_question": "Could you tell me more about what you're looking for?",
            "turn_count": session.turn_count,
        }


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences if a model ever emits them."""
    if text.startswith("```"):
        # e.g. ```json\n{...}\n```
        parts = text.split("```")
        if len(parts) >= 2:
            body = parts[1]
            if body.lstrip().lower().startswith("json"):
                body = body.lstrip()[4:]
            return body.strip()
    return text


# Property-type synonyms -> canonical value accepted by validate_filters.
_PROPERTY_TYPE_SYNONYMS: dict[str, str] = {
    "apartment": "apartment", "apartments": "apartment",
    "flat": "apartment", "flats": "apartment",
    "condo": "apartment", "condos": "apartment", "condominium": "apartment",
    "house": "house", "houses": "house", "home": "house", "homes": "house",
    "studio": "studio", "studios": "studio",
    "villa": "villa", "villas": "villa",
    "penthouse": "penthouse", "penthouses": "penthouse",
    "townhouse": "townhouse", "townhouses": "townhouse", "townhome": "townhouse",
}

_BUY_WORDS = {"buy", "buying", "purchase", "purchasing", "own", "owning", "sale", "sell"}
_RENT_WORDS = {"rent", "renting", "rental", "lease", "leasing"}


def _regex_extract(text: str) -> dict:
    """Lightweight deterministic extractor used as a safety net.

    Tries to pull {city, listing_type, property_type, max_price, bedrooms}
    out of the user's message. All fields are optional.
    """
    out: dict = {}
    if not text:
        return out

    lowered = text.lower()
    tokens = re.findall(r"[a-z]+", lowered)

    if any(w in tokens for w in _BUY_WORDS):
        out["listing_type"] = "buy"
    elif any(w in tokens for w in _RENT_WORDS):
        out["listing_type"] = "rent"

    for tok in tokens:
        if tok in _PROPERTY_TYPE_SYNONYMS:
            out["property_type"] = _PROPERTY_TYPE_SYNONYMS[tok]
            break

    # City: "in <Capitalised Words>" in the ORIGINAL (case-preserved) text.
    # Stop at punctuation or common follower words.
    city_match = re.search(
        r"\bin\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})",
        text,
    )
    if city_match:
        candidate = city_match.group(1).strip()
        stopwords = {"The", "And", "For", "With", "Under", "Below", "Above", "Near"}
        parts = candidate.split()
        kept = []
        for p in parts:
            if p in stopwords:
                break
            kept.append(p)
        if kept:
            out["city"] = " ".join(kept)

    # Max price: "$3000", "3000 dollars", "under 3k", "under 500000".
    price_match = re.search(
        r"(?:under|below|up to|max(?:imum)?|less than|<)\s*\$?\s*([\d,]+)\s*(k|m|thousand|million)?",
        lowered,
    )
    if not price_match:
        price_match = re.search(r"\$\s*([\d,]+)\s*(k|m|thousand|million)?", lowered)
    if price_match:
        raw = price_match.group(1).replace(",", "")
        try:
            val = int(raw)
            suffix = (price_match.group(2) or "").lower()
            if suffix in {"k", "thousand"}:
                val *= 1_000
            elif suffix in {"m", "million"}:
                val *= 1_000_000
            out["max_price"] = val
        except ValueError:
            pass

    # Bedrooms: "2br", "3 bedroom", "2-bed", "two bedroom"
    bed_match = re.search(r"(\d+)\s*(?:br|bed|bedroom|beds|bedrooms|-bed)", lowered)
    if bed_match:
        try:
            out["bedrooms"] = int(bed_match.group(1))
        except ValueError:
            pass

    return out


def _merge_extraction(clarification: dict, extra: dict) -> None:
    """Fill in clarification fields from `extra` where clarification is empty or invalid."""
    for key, value in extra.items():
        current = clarification.get(key)
        is_empty = current in (None, "", [], 0)
        is_invalid_listing = (
            key == "listing_type" and current not in (None, "rent", "buy")
        )
        if is_empty or is_invalid_listing:
            clarification[key] = value


def _missing_required_fields(clarification: dict) -> list[str]:
    """Return which of the three DB-required fields are missing/empty."""
    missing: list[str] = []

    city = clarification.get("city")
    if isinstance(city, str):
        city = city.strip()
    if not city:
        missing.append("city")

    listing_type = clarification.get("listing_type")
    if listing_type not in {"rent", "buy"}:
        missing.append("listing_type")

    max_price = clarification.get("max_price")
    if not max_price:
        missing.append("max_price")

    return missing


def _targeted_follow_up(clarification: dict, missing: list[str]) -> str:
    """Ask only for what's missing, acknowledging what we already know."""
    if not missing:
        return ""

    known_bits: list[str] = []
    listing_type = clarification.get("listing_type")
    property_type = clarification.get("property_type")
    city = clarification.get("city")
    if isinstance(city, str):
        city = city.strip()

    if listing_type in {"rent", "buy"} and property_type:
        known_bits.append(f"a {property_type} to {listing_type}")
    elif property_type:
        known_bits.append(f"a {property_type}")
    elif listing_type in {"rent", "buy"}:
        known_bits.append(f"a place to {listing_type}")

    if city:
        known_bits.append(f"in {city}")

    lead = "Got it"
    if known_bits:
        lead = "Got it - you're looking for " + " ".join(known_bits)

    questions: list[str] = []
    if "city" in missing:
        questions.append("which city or area are you focused on")
    if "listing_type" in missing:
        questions.append("are you looking to rent or to buy")
    if "max_price" in missing:
        if listing_type == "buy":
            questions.append("what's your maximum budget")
        elif listing_type == "rent":
            questions.append("what's your maximum monthly rent")
        else:
            questions.append("what's your budget")

    if len(questions) == 1:
        tail = questions[0] + "?"
    elif len(questions) == 2:
        tail = f"{questions[0]}, and {questions[1]}?"
    else:
        tail = ", ".join(questions[:-1]) + f", and {questions[-1]}?"

    # Capitalise first letter of the tail.
    tail = tail[0].upper() + tail[1:] if tail else tail
    return f"{lead}. {tail}"


_GREETING_WORDS = {
    "hi", "hii", "hiii", "hello", "helo", "hey", "heya", "heyy",
    "hola", "yo", "sup", "howdy", "greetings",
    "goodmorning", "goodafternoon", "goodevening",
}


def _is_pure_greeting(text: str) -> bool:
    """True if the user's message is essentially just a greeting.

    We strip punctuation, collapse whitespace, and check whether every
    remaining token is a known greeting word. Short phrases like "hi",
    "hi there", "hello!!", "hey hey" all return True; anything with real
    content (e.g. "hi, i need an apartment") returns False.
    """
    if not text:
        return False
    cleaned = re.sub(r"[^\w\s]", " ", text).strip().lower()
    if not cleaned:
        return False
    tokens = cleaned.split()
    if len(tokens) > 4:
        return False
    filler = {"there", "bot", "agent", "assistant", "ai"}
    content_tokens = [t for t in tokens if t not in filler]
    if not content_tokens:
        return False
    return all(t in _GREETING_WORDS for t in content_tokens)


def _greeting_reply() -> str:
    return (
        "Hi there! I'm your real estate assistant - I can help you find a "
        "place to rent or buy. What kind of property are you looking for, "
        "and in which city?"
    )


# Short phrases that, on their own, unambiguously end the conversation.
_CLOSER_EXACT_PHRASES: set[str] = {
    "no thanks", "no thank you", "no thankyou", "nope thanks", "nope",
    "not really", "not right now", "not now", "not at the moment",
    "thats all", "that s all", "that is all", "thats it", "that s it", "that is it",
    "im good", "i m good", "i am good", "im fine", "i m fine", "i am fine",
    "im done", "i m done", "i am done", "all good", "all set", "im all set",
    "nothing else", "nothing more", "maybe later", "another time",
    "bye", "goodbye", "good bye", "see you", "see ya", "cya", "take care",
    "thanks", "thank you", "thankyou", "thx", "ty", "cheers", "appreciate it",
    "ok thanks", "okay thanks", "ok thank you", "okay thank you",
    "alright thanks", "cool thanks",
}


def _is_conversation_closer(text: str) -> bool:
    """True if the user's message is essentially closing the conversation.

    We strip punctuation, lower-case, collapse whitespace, then compare
    against a small set of canonical closer phrases. Only short messages
    (<= 6 tokens) are considered, so we don't misfire on e.g.
    "thanks, can you also check Austin?".
    """
    if not text:
        return False
    cleaned = re.sub(r"[^\w\s]", " ", text).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return False
    if len(cleaned.split()) > 6:
        return False
    return cleaned in _CLOSER_EXACT_PHRASES


def _closer_reply(session: SessionState) -> str:
    """Warm sign-off. Mentions the city if one was searched for context."""
    city = None
    try:
        city = session.filter_state.city if session.filter_state else None
    except AttributeError:
        city = None

    if city:
        return (
            f"You're welcome! Best of luck with your search in {city} - "
            "I hope you find the perfect place. Feel free to come back "
            "anytime if you'd like to look at more options."
        )
    return (
        "You're welcome! Feel free to come back anytime if you'd like to "
        "search for more properties. Have a great day!"
    )


def _default_opener(session: SessionState) -> str:
    """A friendly fallback reply used when the model gives us nothing useful."""
    if session.turn_count <= 1:
        return (
            "Hi there! I'm your real estate assistant - I can help you find a "
            "place to rent or buy. What kind of property are you looking for, "
            "and in which city?"
        )
    return (
        "Could you share a bit more about what you're looking for? For example: "
        "the city, whether you want to rent or buy, and your budget."
    )


def _extract_filters(result: dict) -> FilterState:
    return FilterState(
        city=result.get("city"),
        listing_type=result.get("listing_type"),
        min_price=result.get("min_price"),
        max_price=result.get("max_price"),
        bedrooms=result.get("bedrooms"),
        property_type=result.get("property_type"),
        must_have_tags=result.get("must_have_tags") or [],
        nice_to_have_tags=result.get("nice_to_have_tags") or [],
        description_keywords=result.get("description_keywords") or [],
    )


async def _call_synthesis(
    session: SessionState,
    results: list[dict],
    broadening_note: Optional[str],
    system_prompt: str,
) -> str:
    context_lines: list[str] = []
    if broadening_note:
        context_lines.append(f"Note: {broadening_note}")
    context_lines.append(f"Search results ({len(results)} listings found):")
    context_lines.append(json.dumps(results, default=str, indent=2))

    user_payload = (
        f"Conversation so far:\n{_format_history(session)}\n\n"
        f"DB results:\n{chr(10).join(context_lines)}\n\n"
        "Now provide your response to the user based on these results."
    )

    response = await _client.chat.completions.create(
        model=settings.GROK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.6,
        max_tokens=900,
    )
    return (response.choices[0].message.content or "").strip()


def _format_history(session: SessionState) -> str:
    return "\n".join(
        f"{m.role.upper()}: {m.content}" for m in session.messages[-6:]
    )


def _fallback_synthesis(results: list[dict], broadening_note: Optional[str]) -> str:
    """A deterministic reply used only when the Grok API is unreachable."""
    if not results:
        return (
            "I couldn't find any matching listings. Try widening your budget a little, "
            "or let me know if you'd like to search a nearby area."
        )

    lines = [f"I found {len(results)} listings that match your criteria:"]
    if broadening_note:
        lines.append(broadening_note)
    for i, r in enumerate(results[:3], start=1):
        lines.append(
            f"{i}. {r.get('title')} - ${r.get('price'):,} "
            f"({r.get('bedrooms')}br, {r.get('neighbourhood') or r.get('city')})"
        )
    lines.append("Would you like more details on any of these?")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# Tool-call handler (for future native function-calling flow if needed)
# ----------------------------------------------------------------------------
async def handle_tool_call(
    tool_name: str,
    tool_input: dict,
    db_conn: asyncpg.Connection,
    session: SessionState,
) -> dict:
    if tool_name == "search_listings":
        filters = FilterState(**tool_input)
        filters = validate_filters(filters)
        results, note = await execute_search_with_fallback(db_conn, filters)
        return {"results": results, "count": len(results), "broadening_note": note}

    if tool_name == "get_listing_detail":
        listing = await get_listing_by_id(db_conn, tool_input["listing_id"])
        return {"listing": listing}

    if tool_name == "compare_listings":
        listings = await get_listings_by_ids(db_conn, tool_input["listing_ids"])
        return {"listings": listings}

    if tool_name == "save_search":
        saved_id = await save_user_search(db_conn, session.user_id, tool_input)
        return {"saved": True, "id": str(saved_id)}

    return {"error": f"Unknown tool: {tool_name}"}
