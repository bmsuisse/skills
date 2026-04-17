# asyncpg + Postgres Reference

Backend DB layer: **raw asyncpg, no ORM, PEP 750 t-strings for SQL** (Python 3.14).

Load this when writing queries, migrations, connection lifecycle, or transaction logic.

---

## Why no ORM

- Full SQL visibility — no N+1 surprises, no lazy-loading magic.
- Typed at the t-string boundary via the `sql()` helper — values never concatenate into the query.
- asyncpg uses Postgres binary protocol — faster than psycopg3 for most workloads.
- Zero mapping layer — you get `asyncpg.Record` (dict-like) rows; wrap in Pydantic at the response boundary.

---

## The `sql()` helper

Defined in `backend/db.py`:

```python
def sql(template: Template) -> tuple[str, list[object]]:
    parts, params = [], []
    for item in template:
        if isinstance(item, str):
            parts.append(item)
        else:  # Interpolation
            params.append(item.value)
            parts.append(f"${len(params)}")
    return "".join(parts), params
```

Takes a t-string, returns `(query_string, [values])`. Every interpolation becomes a positional param — **there is no string formatting path**, so SQL injection is structurally impossible.

### Usage

```python
from db import pool, sql

async def get_user(user_id: int):
    assert pool is not None
    async with pool.acquire() as conn:
        query, params = sql(t"SELECT id, email FROM users WHERE id = {user_id}")
        return await conn.fetchrow(query, *params)
```

### Dynamic fragments (safe)

T-strings compose. To conditionally add a `WHERE` clause:

```python
async def list_users(search: str | None):
    where = t"TRUE"
    if search:
        where = t"email ILIKE {'%' + search + '%'}"

    # Nest t-strings by interpolating literal strings — but *only* literal SQL,
    # never user input:
    query, params = sql(t"SELECT * FROM users WHERE " + where.strings[0])
    # For real composition use the helper below.
```

For anything beyond trivial dynamic SQL, **write two separate queries**. Don't build a mini query builder.

---

## Connection lifecycle

Pool is created once in `main.py`'s `lifespan`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect()      # opens pool
    yield
    await disconnect()   # closes pool
```

Acquire per request:

```python
async with pool.acquire() as conn:
    row = await conn.fetchrow(...)
```

Pool config (in `db.py`): `min_size=1, max_size=10`. Raise `max_size` for high-concurrency workloads (rule of thumb: ≤ CPU cores × 4).

---

## Query methods

| Method                         | Returns                   | Use when                          |
| ------------------------------ | ------------------------- | --------------------------------- |
| `conn.fetch(q, *params)`       | `list[Record]`            | Multiple rows                     |
| `conn.fetchrow(q, *params)`    | `Record \| None`          | Zero or one row                   |
| `conn.fetchval(q, *params)`    | single value or `None`    | Scalar (count, sum, id)           |
| `conn.execute(q, *params)`     | status string             | INSERT/UPDATE/DELETE, no return   |

`Record` acts like a dict and a tuple: `row["id"]` or `row[0]`.

---

## Transactions

```python
async with pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute(*sql(t"INSERT INTO a (x) VALUES ({x})"))
        await conn.execute(*sql(t"INSERT INTO b (y) VALUES ({y})"))
```

Rollback is automatic on exception.

---

## Common patterns

### Insert + return id

```python
async with pool.acquire() as conn:
    query, params = sql(t"""
        INSERT INTO users (email, name)
        VALUES ({email}, {name})
        RETURNING id
    """)
    user_id = await conn.fetchval(query, *params)
```

### IN clauses with arrays

asyncpg supports Postgres arrays natively — no need to expand manually:

```python
ids = [1, 2, 3]
query, params = sql(t"SELECT * FROM users WHERE id = ANY({ids})")
rows = await conn.fetch(query, *params)
```

### Pagination (keyset, not offset)

Offset pagination is O(n) on the skip; prefer keyset (cursor) pagination for anything > a few pages:

```python
# First page
sql(t"SELECT * FROM posts ORDER BY created_at DESC, id DESC LIMIT {limit}")

# Next page — pass last row's (created_at, id) as cursor
sql(t"""
    SELECT * FROM posts
    WHERE (created_at, id) < ({cursor_ts}, {cursor_id})
    ORDER BY created_at DESC, id DESC
    LIMIT {limit}
""")
```

### Upsert

```python
sql(t"""
    INSERT INTO users (email, name) VALUES ({email}, {name})
    ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
""")
```

---

## Migrations

Not scaffolded — pick per project:

- **yoyo-migrations** (`uv add yoyo-migrations`) — plain SQL files + CLI, minimal, great fit for this stack.
- **dbmate** — single binary, runs outside Python.
- **Raw SQL + `schema.sql`** — simplest; apply manually or via CI. Fine for small projects.

Do **not** add Alembic — it's tied to SQLAlchemy metadata which we don't use.

---

## Mapping to Pydantic

At the response boundary, wrap records:

```python
from pydantic import BaseModel

class UserOut(BaseModel):
    id: int
    email: str
    name: str

@app.get("/users/{user_id}", response_model=UserOut)
async def read_user(user_id: int) -> UserOut:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(*sql(t"SELECT id, email, name FROM users WHERE id = {user_id}"))
    if row is None:
        raise HTTPException(404)
    return UserOut(**dict(row))
```

FastAPI's `response_model` drives the OpenAPI schema, which `openapi-typescript` turns into frontend types.
