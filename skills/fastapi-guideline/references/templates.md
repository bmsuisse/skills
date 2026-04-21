# FastAPI Project Templates

> Source: `bunx skills add https://github.com/wshobson/agents --skill fastapi-templates` (recommended) / `npx skills add ...`

Production-ready FastAPI structures with async patterns, dependency injection, middleware.

**Database:** uses psycopg directly (no ORM). See the `postgres-best-practices` skill for all DB patterns — this file covers the FastAPI-specific wiring only.

---

## Project layout

```
app/
├── api/
│   ├── v1/
│   │   ├── endpoints/      # Route handlers (all async def)
│   │   └── router.py
│   └── dependencies.py     # Shared Depends()
├── core/
│   ├── config.py           # Settings via pydantic-settings
│   └── security.py         # JWT, password hashing
├── db/
│   ├── connection.py       # AsyncConnectionPool + get_pg_connection()
│   ├── postgres.py         # pg_* CRUD helpers
│   ├── loader.py           # load_sql()
│   ├── queries/            # .sql files per topic
│   └── repositories/       # One file per domain
├── models/                 # Pydantic models (PostgresTableModel + BaseModel)
├── schemas/                # FastAPI request/response schemas
└── main.py                 # App entry point with lifespan
```

---

## Settings (pydantic-settings)

```python
# core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PG_HOST: str
    PG_PORT: int = 5432
    PG_DB: str
    PG_USER: str
    PG_PASSWORD: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_V1_STR: str = "/api/v1"

    model_config = {"env_file": ".env"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

---

## Database connection (psycopg pool)

```python
# db/connection.py
from __future__ import annotations
import os
from psycopg_pool import AsyncConnectionPool

_PREFIX = os.getenv("PG_ENV_PREFIX", "POSTGRES_")

def _dsn() -> str:
    p = _PREFIX
    return (
        f"host={os.environ[p + 'HOST']} "
        f"port={os.environ[p + 'PORT']} "
        f"dbname={os.environ[p + 'DB']} "
        f"user={os.environ[p + 'USER']} "
        f"password={os.environ[p + 'PASSWORD']}"
    )

_pool: AsyncConnectionPool | None = None

async def open_pool() -> None:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=_dsn,
            open=False,
            max_size=40,
            check=AsyncConnectionPool.check_connection,
        )
    if not _pool._opened:
        await _pool.open()

def get_pg_connection():
    """Return an async connection context manager from the pool."""
    assert _pool is not None, "Call open_pool() first (e.g. in app lifespan)."
    return _pool.connection()
```

Wire the pool into the app lifespan:

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.connection import open_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield

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

## Repository pattern

Repositories call `get_pg_connection()` directly — no FastAPI `Depends` needed for DB access. Use the `pg_*` helpers for simple CRUD; write `.sql` files for everything custom.

```python
# db/repositories/item_repository.py
from __future__ import annotations
from psycopg.rows import dict_row
from app.db.connection import get_pg_connection
from app.db.postgres import pg_retrieve, pg_insert, pg_delete
from app.db.loader import load_sql
from app.models.item_models import ItemRow, ItemSummary

class ItemRepository:
    async def get_by_id(self, item_id: int) -> ItemRow | None:
        async with get_pg_connection() as conn:
            return await pg_retrieve(conn, ItemRow, {"id": item_id})

    async def list_active(self, limit: int = 100) -> list[ItemSummary]:
        sql = load_sql("items", "list_active_items")
        async with get_pg_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, {"limit": limit})
                rows = await cur.fetchall()
        return [ItemSummary.model_validate(r) for r in rows]

    async def create(self, data: dict) -> ItemRow:
        async with get_pg_connection() as conn:
            row = await pg_insert(conn, ItemRow.get_table_name(), data)
        return ItemRow.model_validate(row)

    async def delete(self, item: ItemRow) -> ItemRow | None:
        async with get_pg_connection() as conn:
            return await pg_delete(conn, item, ItemRow)

item_repository = ItemRepository()
```

---

## Pydantic models

```python
# models/item_models.py
from __future__ import annotations
from datetime import datetime
from typing import Sequence
from pydantic import BaseModel, ConfigDict
from app.db.pg_base import PostgresTableModel

class ItemRow(PostgresTableModel):
    """Full items table row — use with pg_* helpers."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    created_at: datetime

    @staticmethod
    def get_table_name() -> tuple[str, str]:
        return ("public", "items")

    @staticmethod
    def get_primary_key() -> Sequence[str]:
        return ["id"]

class ItemSummary(BaseModel):
    """Partial result — for list views / joins."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
```

FastAPI request/response schemas live separately in `schemas/`:

```python
# schemas/item.py
from pydantic import BaseModel

class ItemCreate(BaseModel):
    name: str
    description: str | None = None

class ItemResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    description: str | None
```

---

## Endpoint example

```python
# api/v1/endpoints/items.py
from fastapi import APIRouter, HTTPException
from app.db.repositories.item_repository import item_repository
from app.schemas.item import ItemCreate, ItemResponse

router = APIRouter()

@router.get("/", response_model=list[ItemResponse])
async def list_items(limit: int = 100) -> list[ItemResponse]:
    return await item_repository.list_active(limit=limit)

@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int) -> ItemResponse:
    item = await item_repository.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(item_in: ItemCreate) -> ItemResponse:
    return await item_repository.create(item_in.model_dump())

@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int) -> None:
    item = await item_repository.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await item_repository.delete(item)
```

---

## Router setup

```python
# api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import items, users, auth

api_router = APIRouter()
# Note: route paths should NOT repeat the prefix set here
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
```

---

## JWT auth dependency

```python
# api/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import settings
from app.db.repositories.user_repository import user_repository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserRow:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: int = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    user = await user_repository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

CurrentUser = Annotated[UserRow, Depends(get_current_user)]
```

---

## Testing setup

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app

@pytest.fixture
async def client():
    # Patch the pool so tests don't need a real DB unless you want integration tests
    with patch("app.db.connection._pool") as mock_pool:
        mock_pool._opened = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
```

For integration tests hitting a real DB, see the `postgres-test-setup` skill.

---

## Background tasks

```python
from fastapi import BackgroundTasks

async def send_notification(email: str, message: str) -> None:
    await email_client.send(email, message)

@router.post("/items/", response_model=ItemResponse, status_code=201)
async def create_item(
    item_in: ItemCreate,
    background_tasks: BackgroundTasks,
) -> ItemResponse:
    item = await item_repository.create(item_in.model_dump())
    background_tasks.add_task(send_notification, item.owner_email, f"Item {item.id} created")
    return item
```
