---
title: FastAPI
description: Production FastAPI patterns — lifespan, dependency injection, async Postgres, streaming.
---

# FastAPI

**Skill:** `fastapi-guideline` · **Plugin:** `coding@bmsuisse-skills`

## Setup

```bash
uv add fastapi granian asyncpg pydantic-settings
# Do NOT use fastapi[standard] — it bundles uvicorn which conflicts with Granian
```

Run dev server:

```bash
uv run granian --interface asgi main:app --reload
```

## App structure

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import init_pool, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()

app = FastAPI(lifespan=lifespan)
```

## Dependency injection

```python
from fastapi import Depends
from asyncpg import Connection
from db import pool

async def get_conn() -> AsyncGenerator[Connection, None]:
    async with pool.acquire() as conn:
        yield conn

@app.get("/users/{id}")
async def get_user(id: str, conn: Connection = Depends(get_conn)):
    return await conn.fetchrow(*sql(t"SELECT * FROM users WHERE id = {id}"))
```

## Request / response models

```python
from pydantic import BaseModel

class CreateUser(BaseModel):
    email: str
    name: str

class User(BaseModel):
    id: str
    email: str
    name: str

@app.post("/users", response_model=User, status_code=201)
async def create_user(body: CreateUser, conn: Connection = Depends(get_conn)):
    row = await conn.fetchrow(*sql(
        t"INSERT INTO users (email, name) VALUES ({body.email}, {body.name}) RETURNING *"
    ))
    return User(**row)
```

## CORS

Pre-configured for `http://localhost:5173` (Vite default). Update for production:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## SSE streaming

```python
from fastapi.responses import StreamingResponse
import asyncio

async def event_stream(prompt: str):
    async for chunk in llm.stream(prompt):
        yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"

@app.get("/stream")
async def stream(prompt: str):
    return StreamingResponse(event_stream(prompt), media_type="text/event-stream")
```

## Type checking

```bash
uv add --dev ty
uv run ty check
```
