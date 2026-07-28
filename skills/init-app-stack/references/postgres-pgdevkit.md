# pgdevkit + Postgres Reference

Backend DB layer: **[pgdevkit](https://github.com/bmsuisse/pgdevkit) (psycopg), no ORM.**

Load this when writing queries, adding tables, or touching connection lifecycle. For
the full convention (not just this scaffold's slice of it), install and read
pgdevkit's own skill: `skillup add bmsuisse/pgdevkit --skill pgdevkit` — that skill,
not this file, is the source of truth; this file only covers how the scaffold wires
it up.

---

## Why no ORM

- Full SQL visibility — no N+1 surprises, no lazy-loading magic.
- Named `%(name)s` params via psycopg — values never touch string concatenation.
- Zero mapping layer for simple cases — `pgdevkit.db`'s `pg_*` helpers map rows
  straight to Pydantic models declared on the model itself (`get_table_name()`,
  `get_primary_key()`).

---

## Connection lifecycle

The pool lives in `backend/db.py`:

```python
from pgdevkit.db import PgPool

pool = PgPool(env_prefix="APP_POSTGRES_")
```

`env_prefix="APP_POSTGRES_"` must match `[tool.pgdevkit] env_prefix = "APP_"` in
`pyproject.toml` + `"POSTGRES_"` — that's what lets the same pool read either the
docker-compose dev database's env vars (`.env` → `APP_POSTGRES_HOST/PORT/DB/USER/PASSWORD`)
or, under pytest, the per-branch test database `ensure_testdb()` sets up (see below).

Opened/closed once in `main.py`'s `lifespan`:

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    await pool.open()
    yield
    await pool.close()
```

Acquire per request:

```python
async with pool.connection() as conn:
    row = await (await conn.execute("SELECT 1")).fetchone()
```

---

## Models

Table-mapped models extend `PostgresTableModel`; partial results (joins,
aggregations) extend `BaseModel` directly:

```python
from pydantic import BaseModel, ConfigDict
from pgdevkit.db import PostgresTableModel

class UserRow(PostgresTableModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str

    @staticmethod
    def get_table_name() -> tuple[str, str]:
        return ("public", "users")

    @staticmethod
    def get_primary_key() -> list[str]:
        return ["id"]
```

---

## CRUD helpers

```python
from pgdevkit.db import pg_retrieve, pg_retrieve_many, pg_insert, pg_upsert, pg_delete
```

| Helper | Purpose |
|---|---|
| `pg_retrieve` | Fetch single row by PK |
| `pg_retrieve_many` | Fetch rows matching a filter dict |
| `pg_insert` | Insert one row, `RETURNING *` |
| `pg_update` / `pg_update_dict` | Update by PK |
| `pg_upsert` / `pg_upsert_dict` | `INSERT ... ON CONFLICT ... DO UPDATE` |
| `pg_delete` / `pg_delete_dict` | Delete by PK, returns deleted row |

```python
async with pool.connection() as conn:
    user = await pg_retrieve(conn, UserRow, {"id": user_id})
```

For custom `WHERE` clauses, joins, aggregations, or ordering, write a dedicated
`.sql` file instead of composing one of these helpers further.

---

## Custom queries — `.sql` files

Trivial queries (**4 lines or fewer**) may be inline Python strings with named
params. Anything with joins/CTEs/aggregations/subqueries gets its own file under
`backend/db/queries/<topic>/`:

```python
# backend/db/loader.py
from pathlib import Path
from pgdevkit.db import SqlLoader

sql = SqlLoader(Path(__file__).parent / "queries")
```

```python
# backend/db/queries/users/list_active_users.sql
SELECT id, email, name FROM users WHERE is_active = %(is_active)s ORDER BY id
```

```python
rows = await (await conn.execute(sql.load_sql("users", "list_active_users"), {"is_active": True})).fetchall()
```

Always named `%(name)s` params with a dict argument — never positional `%s`,
never f-strings or `.format()` for SQL text.

---

## The `database/` folder — schema as code

`database/` is the source of truth for the schema — plain `.sql` files, one object
per file, grouped into layer directories (per schema/domain) and object-type
subfolders (`tables/`, `views/`, `scalar_functions/`, ...) that control apply
order. Full convention: pgdevkit's `docs/database-layout.md`.

```
database/
├── 0_app/
│   ├── tables/
│   │   └── users.sql
│   └── views/
├── migrations/
│   └── 2026-07-10_add_users_email_index.sql
```

`pgdb testdb up` applies every file here to the local/CI test database.
`migrations/` is skipped by `pgdb testdb` on purpose — update the table/view's own
`.sql` file in the same change so it never drifts from what a migration did to
production.

---

## Tests

`tests/conftest.py` (already scaffolded):

```python
import os
import pytest
from pgdevkit.testdb import ensure_testdb

@pytest.fixture(scope="session", autouse=True)
def _testdb_env():
    env = ensure_testdb()
    for key, value in env.items():
        os.environ[key] = value
```

`ensure_testdb()` starts the shared `pgdevkit-postgres` container if needed
(Docker or Podman, no CLI binary required), creates a database scoped to this
project+branch, and applies `database/` to it. Because it sets the *same*
`APP_POSTGRES_*` env vars the app's `pool` reads, tests can exercise `backend.db.pool`
directly against the real (test) schema instead of mocking the database:

```python
from backend.db import pool

async def test_db_connection():
    await pool.open()
    try:
        async with pool.connection() as conn:
            row = await (await conn.execute("SELECT 1 AS ok")).fetchone()
        assert row[0] == 1
    finally:
        await pool.close()
```

Run with `just test`.

---

## Mapping to Pydantic at the response boundary

```python
class UserOut(BaseModel):
    id: int
    email: str
    name: str

@app.get("/users/{user_id}", response_model=UserOut)
async def read_user(user_id: int) -> UserOut:
    async with pool.connection() as conn:
        user = await pg_retrieve(conn, UserRow, {"id": user_id})
    if user is None:
        raise HTTPException(404)
    return UserOut(**user.model_dump())
```

FastAPI's `response_model` drives the OpenAPI schema, which `openapi-typescript`
turns into frontend types.

---

## Backfilling / drift

If a table was created directly on a live database and never got a `.sql` file,
or you need to check `database/` against reality:

```bash
pgdb fetch-missing database/ --url postgresql://... --write   # reverse-engineer missing DDL
pgdb compare --url postgresql://... database/                 # report drift
```
