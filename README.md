# Real Estate Chat Agent

A natural-language property-search assistant built with **FastAPI**, **PostgreSQL**,
**Redis**, **Grok (xAI)** and **React**.

The agent asks clarifying questions, extracts structured filters from free text,
runs a parameterised SQL query against a catalogue of listings, and replies
conversationally with matched properties.

```
words -> Grok JSON -> validation -> query builder -> parameterised SQL -> PostgreSQL
```

---

## Architecture

| Layer          | Tech                                  |
| -------------- | ------------------------------------- |
| LLM            | Grok (xAI) via OpenAI-compatible API  |
| Backend        | Python 3.11 + FastAPI (async)         |
| Database       | PostgreSQL 16 (GIN + full-text search)|
| Session memory | Redis 7                               |
| Background     | Celery + Celery Beat                  |
| Frontend       | React 18 + Vite                       |
| Deployment     | Docker Compose                        |

Voice (optional): Twilio Media Streams + Deepgram STT + ElevenLabs TTS.

---

## Project layout

```
realestate_agent/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings loaded from .env
│   ├── database.py              # asyncpg pool
│   ├── redis_client.py          # Redis session store
│   ├── models/                  # Pydantic models (listing, session, filters)
│   ├── agent/
│   │   ├── orchestrator.py      # LLM + DB agent loop
│   │   ├── prompts.py           # System prompts
│   │   ├── tools.py             # Tool schemas (function calling)
│   │   ├── tag_vocabulary.py    # Approved tag list
│   │   └── deepgram_stt.py      # Voice STT connector
│   ├── db/
│   │   ├── query_builder.py     # Filter -> parameterised SQL
│   │   ├── listing_repo.py      # All DB queries
│   │   └── migrations/
│   │       ├── 001_initial.sql  # Schema
│   │       └── 002_seed_data.sql# 25 dummy listings + agents + demo user
│   ├── routers/
│   │   ├── chat.py              # POST /api/chat + WS /api/ws/chat
│   │   └── voice.py             # WS /voice/ws/voice (Twilio)
│   ├── workers/                 # Celery app + tasks
│   ├── scripts/load_dummy_data.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx
│   │   │   ├── MessageBubble.jsx
│   │   │   ├── PropertyCard.jsx
│   │   │   ├── PropertyList.jsx
│   │   │   └── MapView.jsx
│   │   ├── hooks/useWebSocket.js
│   │   └── api/chat.js
│   └── package.json
├── docker-compose.yml
└── .env.example
```

---

## 1. Configure environment

```bash
cp .env.example .env
```

Then open `.env` and replace the placeholders with your real keys. **All API
keys are placeholders by default** — the app will start without them, but the
LLM call will fail until you drop in a real Grok key.

Required:
- `GROK_API_KEY` — get a free key at [console.x.ai](https://console.x.ai/)

Optional (voice):
- `DEEPGRAM_API_KEY`
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`

Optional (map):
- `VITE_MAPBOX_TOKEN`

---

## 2. Run with Docker (recommended)

```bash
docker compose up --build
```

This starts:
- `postgres` on `5432` (auto-applies `001_initial.sql` and `002_seed_data.sql` on first boot)
- `redis` on `6379`
- `backend` on `8000` (FastAPI + Uvicorn)
- `worker` — Celery worker
- `beat` — Celery beat scheduler
- `frontend` on `5173` (Vite dev server)

Open **http://localhost:5173** in your browser.

> The migrations in `backend/db/migrations/` are mounted read-only into the
> official Postgres container at `/docker-entrypoint-initdb.d/`, which is
> Postgres's standard bootstrap mechanism — all `.sql` files are executed in
> alphabetical order on the **first** container start.

If you ever want to wipe and reseed:

```bash
docker compose down -v   # removes postgres volume
docker compose up --build
```

---

## 3. Run locally without Docker

You'll need Python 3.11+, Node 20+, a running PostgreSQL and a running Redis.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Load dummy data
python -m backend.scripts.load_dummy_data

# Run API
uvicorn backend.main:app --reload

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

---

## 4. Loading / replacing data

### Dummy data
We ship 25 curated listings across Austin, New York, Miami, San Francisco,
Seattle, Denver, Chicago and London, spanning every tag category. They're in
`backend/db/migrations/002_seed_data.sql` and are inserted automatically.

### Adding your own listings
Option A — append SQL:
```sql
INSERT INTO listings (title, listing_type, property_type, price, bedrooms, city, tags, images)
VALUES ('My loft', 'rent', 'apartment', 2000, 1, 'Austin',
        ARRAY['exposed_brick','balcony'], ARRAY['https://…']);
```

Option B — use the Python repo:
```python
from backend.database import get_db_conn_context
async with get_db_conn_context() as conn:
    await conn.execute("INSERT INTO listings (...) VALUES (...)", ...)
```

> Tag values **must** come from `backend/agent/tag_vocabulary.py` — they're the
> only ones the agent knows how to ask for.

---

## 5. API

### HTTP
```
POST /api/chat
{
  "message": "3-bedroom apartment in Austin under $2,500/month with a garage",
  "session_id": "optional-uuid"
}
```
Response:
```json
{
  "reply": "I found 2 great matches…",
  "session_id": "uuid",
  "listings": [ {...}, {...} ],
  "filters":  { "city": "Austin", "max_price": 2500, ... }
}
```

### WebSocket
```
WS /api/ws/chat/{session_id}

→ client sends: {"message": "..."}
← server sends: {"type": "reply", "content": "..."} then {"type": "listings", "data": [...]}
```

### Reset session
```
DELETE /api/chat/{session_id}
```

---

## 6. How the agent decides when to search

1. **Clarify** — Grok reads the full chat history and returns a JSON object. If
   it's missing `city`, `listing_type` or `max_price` it returns a follow-up
   question and increments the turn counter.
2. **Validate** — `backend/db/query_builder.validate_filters()` throws if any
   extracted field is out of range or uses an unknown tag.
3. **Query** — `execute_search_with_fallback()` runs the exact query first,
   then progressively broadens (price +20%, drop last must-have tag, drop
   bedroom count) if results are empty.
4. **Synthesise** — Grok turns raw rows into a friendly reply, limited to 3
   listings (chat) or 2 (voice).

All SQL is parameterised — the LLM never sees or writes raw SQL.

---

## 7. Extending

- **Add a new tag** → edit `backend/agent/tag_vocabulary.py` and add it to any
  seed listings. The agent will start using it on next turn.
- **Add a new tool** → add it to `TOOLS` in `backend/agent/tools.py` and
  handle it in `orchestrator.handle_tool_call`.
- **Notifications** → fill in `workers/tasks.py::send_listing_notification`
  with your email provider.

---

## 8. Tests

```bash
# quick smoke
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"3BR apartment in Austin under $2500/month"}'
```
