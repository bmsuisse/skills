---
name: fastapi-guideline
plugin: coding
description: >
  Use this skill whenever working with FastAPI — building APIs, adding routes, structuring projects,
  streaming responses, handling authentication, database access, or running the server.
  Triggers on: "fastapi", "build an API", "add an endpoint", "stream response", "SSE", "server-sent events",
  "async endpoint", "dependency injection", "pydantic model", "granian", or any backend API work in Python.
  Always use this skill when the user is writing or modifying a FastAPI application, even if they don't say "FastAPI" explicitly.
---

# FastAPI Skill

Production-ready FastAPI with async-first patterns, Granian as the server, and native SSE streaming.

> Base patterns sourced from:
> `npx skills add https://github.com/wshobson/agents --skill fastapi-templates`
> Extended with Granian server, native SSE (FastAPI 0.135.0+), and additional async conventions.

## Core rules — apply always

1. **Every function must be `async def`.** No sync route handlers, no sync service methods, no sync repository methods. If you call a blocking library, wrap it with `asyncio.to_thread()`.
2. **Granian is the server.** Never use `uvicorn` or `fastapi dev`. See [`references/granian.md`](references/granian.md).
3. **SSE streaming** uses the native `EventSourceResponse` from `fastapi.sse` (added in FastAPI 0.135.0). Never use third-party `sse-starlette`. See [`references/sse.md`](references/sse.md).
4. **Always use `uv`** for dependency management. Never pip, poetry, or pipenv.
5. **No ORM.** Database access uses psycopg directly via `AsyncConnectionPool`. Follow the `postgres-best-practices` skill for all DB patterns (queries in `.sql` files, `pg_*` helpers, `PostgresTableModel`, named parameters).

---

## Project structure

```
app/
├── api/
│   ├── v1/
│   │   ├── endpoints/      # Route handlers (all async def)
│   │   └── router.py
│   └── dependencies.py     # Shared Depends()
├── core/
│   ├── config.py           # Settings via pydantic-settings
│   ├── security.py         # JWT, password hashing
│   └── database.py         # Async SQLAlchemy session
├── models/                 # ORM models
├── schemas/                # Pydantic schemas
├── services/               # Business logic (all async)
├── repositories/           # Data access layer (all async)
└── main.py                 # App entry point with lifespan
```

---

## main.py — app factory with lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.disconnect()

app = FastAPI(title="API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")
```

---

## Running the server — always Granian

```bash
uv add granian
uv run granian --interface asgi main:app --port 8000 --workers 1
```

For development with auto-reload:

```bash
uv add granian[reload]
uv run granian --interface asgi main:app --reload
```

Full Granian details: [`references/granian.md`](references/granian.md)

---

## Reference files (load as needed)

| File | When to read |
|------|-------------|
| [`references/templates.md`](references/templates.md) | Project structure, psycopg pool wiring, repos, DI, auth, testing |
| [`references/sse.md`](references/sse.md) | SSE streaming endpoints — AI chat, live updates, logs |
| [`references/granian.md`](references/granian.md) | Granian CLI options, workers, HTTP/2, event loop config |

For DB patterns (SQL files, `pg_*` helpers, `PostgresTableModel`, named params, dynamic SQL), always consult the **`postgres-best-practices`** skill.

---

## Quick patterns

### Async route (no Depends for DB — repos call `get_pg_connection()` directly)

```python
@router.get("/items/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    item = await item_repository.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

### Async service calling blocking code

```python
import asyncio

async def read_file(path: str) -> str:
    return await asyncio.to_thread(Path(path).read_text)
```

### SSE streaming (AI chat pattern)

```python
from collections.abc import AsyncIterable
from fastapi.sse import EventSourceResponse, ServerSentEvent

@router.post("/chat/stream", response_class=EventSourceResponse)
async def stream_chat(prompt: Prompt) -> AsyncIterable[ServerSentEvent]:
    async for token in llm_stream(prompt.text):
        yield ServerSentEvent(data=token, event="token")
    yield ServerSentEvent(raw_data="[DONE]", event="done")
```

Full SSE details: [`references/sse.md`](references/sse.md)

---

## pyproject.toml scripts section

```toml
[tool.uv.scripts]
dev = "granian --interface asgi main:app --reload"
start = "granian --interface asgi main:app --workers 4"
```

Run with: `uv run dev`
