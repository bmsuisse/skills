---
title: Postgres
description: Raw asyncpg patterns for Python — connection pool, t-string SQL helper, transactions, pagination.
---

# Postgres

**Skills:** `postgres-best-practices`, `postgres-test-setup` · **Plugin:** `coding@bmsuisse-skills`

No ORM. Raw asyncpg with t-string SQL helpers.

## Connection pool

```python
# db.py
import asyncpg
from config import settings

pool: asyncpg.Pool | None = None

async def init_pool() -> None:
    global pool
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)

async def close_pool() -> None:
    if pool:
        await pool.close()
```

## T-string SQL helper

Python 3.14 t-strings for injection-safe parameterized queries:

```python
from string.templatelib import Template

def sql(query: Template) -> tuple[str, *tuple[object, ...]]:
    parts, params = [], []
    for item in query:
        if isinstance(item, str):
            parts.append(item)
        else:
            params.append(item.value)
            parts.append(f"${len(params)}")
    return ("".join(parts), *params)

# Usage
user_id = "abc-123"
rows = await conn.fetch(*sql(t"SELECT * FROM users WHERE id = {user_id}"))
# → "SELECT * FROM users WHERE id = $1", "abc-123"
```

## Queries

```python
async with pool.acquire() as conn:
    # single row
    row = await conn.fetchrow(*sql(t"SELECT * FROM users WHERE id = {id}"))

    # multiple rows
    rows = await conn.fetch(*sql(t"SELECT * FROM users WHERE active = {True}"))

    # insert returning
    new = await conn.fetchrow(*sql(
        t"INSERT INTO users (email, name) VALUES ({email}, {name}) RETURNING *"
    ))

    # scalar
    count = await conn.fetchval(*sql(t"SELECT count(*) FROM users"))
```

## Transactions

```python
async with pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute(*sql(t"UPDATE accounts SET balance = balance - {amount} WHERE id = {from_id}"))
        await conn.execute(*sql(t"UPDATE accounts SET balance = balance + {amount} WHERE id = {to_id}"))
```

## Pagination

```python
async def list_users(page: int, size: int = 20) -> list[dict]:
    offset = (page - 1) * size
    rows = await conn.fetch(*sql(
        t"SELECT * FROM users ORDER BY created_at DESC LIMIT {size} OFFSET {offset}"
    ))
    return [dict(r) for r in rows]
```

## Test setup

For integration tests, use a real Postgres database (not mocks):

```bash
docker compose up -d db
uv run pytest
```

The `postgres-test-setup` skill provides fixtures for creating isolated test schemas per test run.
