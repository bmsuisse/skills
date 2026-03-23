---
name: postgres-best-practices
description: >
  PostgreSQL coding standards for Python projects using psycopg (no ORM). Use
  this skill whenever the user is writing or reviewing code that queries
  PostgreSQL with psycopg, creates SQL files, maps query results to Python
  objects, or asks how to structure database access code. Triggers on things
  like "add a database query", "write a SQL query", "create a repository",
  "fetch from postgres", "insert into the database", "update the DB",
  "parameterised query", "pydantic model from DB row", "sql file", "dynamic
  SQL", or any mention of psycopg, psycopg2, asyncpg, or SQLAlchemy where the
  user seems open to a different approach. Also use when the user asks about
  connection pooling, transactions, cursor factories, or how to organise
  database code.
---

# PostgreSQL Best Practices (psycopg, no ORM)

Core rules for every piece of database code in this project:

- **No ORM** — use [psycopg](https://www.psycopg.org/psycopg3/) directly.
- **No inline SQL** — every custom query lives in its own `.sql` file.
- **Named parameters** — always `%(name)s` style, never positional `%s`.
- **SQL formatting** — all `.sql` files are formatted with [shandy-sqlfmt](https://sqlfmt.com/).
- **Dynamic SQL** — check `pyproject.toml` for the Python version; use psycopg t-string templates on 3.14+, otherwise `psycopg.sql`.
- **Result mapping** — every query result maps to a Pydantic model defined in a `{topic}_models.py` file.

---

## Project layout

```
app/
├── db/
│   ├── connection.py          # pool factory + get_pg_connection()
│   ├── postgres.py            # generic pg_* CRUD helpers
│   ├── loader.py              # load_sql() helper
│   ├── queries/
│   │   ├── users/
│   │   │   ├── get_user_by_id.sql
│   │   │   └── list_active_users.sql
│   │   └── orders/
│   │       └── list_orders_by_user.sql
│   └── repositories/
│       ├── user_repository.py
│       └── order_repository.py
├── models/
│   ├── user_models.py         # Pydantic models for user domain
│   └── order_models.py        # Pydantic models for order domain
```

SQL files live under `db/queries/<topic>/`. Every custom query gets its own file — no multi-statement files that lump unrelated queries together.

---

## Connection & pool

The env-var prefix (`POSTGRES_`) should be adjusted to match the project (e.g. `APP_POSTGRES_`, `MDM_POSTGRES_`).

`_pool` is intentional module-level mutable state

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
        _pool = AsyncConnectionPool(conninfo=_dsn, open=False, max_size=40, check=AsyncConnectionPool.check_connection)
    if not _pool._opened:
        await _pool.open()

def get_pg_connection():
    """Return an async connection context manager from the pool."""
    assert _pool is not None, "Call open_pool() first (e.g. in app startup)."
    return _pool.connection()
```

---

## Base model — `PostgresTableModel`

Models that map 1:1 to a DB table extend `PostgresTableModel`. This lets the generic helpers below know which table and which columns are PKs:

```python
# db/pg_base.py
from abc import ABC
from typing import Sequence
from pydantic import BaseModel

class PostgresTableModel(BaseModel, ABC):
    @staticmethod
    def get_table_name() -> tuple[str, str]:
        """Return (schema, table) e.g. ('public', 'users')."""
        ...

    @staticmethod
    def get_primary_key() -> Sequence[str]:
        """Return the PK column name(s) as a sequence."""
        ...
```

Topic models that represent a full table row inherit from `PostgresTableModel`:

```python
# models/user_models.py
from db.pg_base import PostgresTableModel

class UserRow(PostgresTableModel):
    id: int
    email: str
    display_name: str
    created_at: datetime

    @staticmethod
    def get_table_name() -> tuple[str, str]:
        return ("public", "users")

    @staticmethod
    def get_primary_key() -> Sequence[str]:
        return ["id"]
```

Models that represent partial results (e.g. from a JOIN) just extend `BaseModel` directly — they are not table models.

---

## Generic CRUD helpers — `db/postgres.py`

Copy this file into the project and strip any project-specific bits. These helpers cover the common CRUD patterns so you don't have to write boilerplate SQL for simple operations:

```python
# db/postgres.py
from __future__ import annotations

from typing import Any, Sequence, TypeVar, Type, Optional, Callable, Mapping
from psycopg.connection_async import AsyncConnection
from psycopg.sql import SQL, Identifier, Placeholder
from psycopg.rows import dict_row
from db.pg_base import PostgresTableModel

T = TypeVar("T", bound=PostgresTableModel)


async def pg_retrieve(con: AsyncConnection, data_type: Type[T], pks: dict) -> T | None:
    """Fetch a single row by primary key(s)."""
    async with con.cursor(row_factory=dict_row) as cur:
        schema, table = data_type.get_table_name()
        where = " AND ".join(f"{pk} = %({pk})s" for pk in pks)
        await cur.execute(f"select * from {schema}.{table} where {where}", pks)  # type: ignore[arg-type]
        row = await cur.fetchone()
    return data_type(**row) if row else None


async def pg_retrieve_many(
    con: AsyncConnection,
    data_type: Type[T],
    filters: dict,
    *,
    from_dict: Optional[Callable[[Mapping], T]] = None,
) -> Sequence[T]:
    """Fetch multiple rows matching all filter key=value pairs."""
    async with con.cursor(row_factory=dict_row) as cur:
        schema, table = data_type.get_table_name()
        if filters:
            where = " AND ".join(f"{k} = %({k})s" for k in filters)
            sql = f"select * from {schema}.{table} where {where}"  # type: ignore[assignment]
        else:
            sql = f"select * from {schema}.{table}"  # type: ignore[assignment]
        await cur.execute(sql, filters)
        rows = await cur.fetchall()
    fn = from_dict or (lambda d: data_type(**d))
    return [fn(r) for r in rows]


async def pg_insert(con: AsyncConnection, table_name: tuple[str, str], data: dict) -> dict[str, Any]:
    """Insert one row and return the full row (RETURNING *)."""
    query = SQL("INSERT INTO {tbl} ({cols}) VALUES ({vals}) RETURNING *").format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in data),
        vals=SQL(", ").join(Placeholder(k) for k in data),
    )
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, data)
        row = await cur.fetchone()
    assert row is not None
    return row


async def pg_update_dict(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: dict,
    primary_keys: Sequence[str],
) -> Any | None:
    """Update a row identified by primary_keys. Returns the raw row tuple."""
    set_parts = [
        SQL("{col} = {val}").format(col=Identifier(k), val=Placeholder(k))
        for k in data if k not in primary_keys
    ]
    where_parts = [
        SQL("{col} = {val}").format(col=Identifier(pk), val=Placeholder(pk))
        for pk in primary_keys
    ]
    query = SQL("UPDATE {tbl} SET {sets} WHERE {where} RETURNING *").format(
        tbl=Identifier(*table_name),
        sets=SQL(", ").join(set_parts),
        where=SQL(" AND ").join(where_parts),
    )
    async with con.cursor() as cur:
        await cur.execute(query, data)
        return await cur.fetchone()


async def pg_update(con: AsyncConnection, data: T, data_type: type[T]) -> Any | None:
    """Update a typed model instance."""
    return await pg_update_dict(con, data_type.get_table_name(), data.model_dump(), data_type.get_primary_key())


async def pg_upsert_dict(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: dict,
    primary_keys: Sequence[str],
) -> dict:
    """INSERT … ON CONFLICT … DO UPDATE, returns the row as a dict."""
    fields = list(data)
    updates = [SQL("{col} = EXCLUDED.{col}").format(col=Identifier(k)) for k in fields]
    query = SQL(
        "INSERT INTO {tbl} ({cols}) VALUES ({vals}) ON CONFLICT ({pks}) DO UPDATE SET {updates} RETURNING *"
    ).format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in fields),
        vals=SQL(", ").join(Placeholder(k) for k in fields),
        pks=SQL(", ").join(Identifier(pk) for pk in primary_keys),
        updates=SQL(", ").join(updates),
    )
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, data)
        row = await cur.fetchone()
    assert row is not None
    return row


async def pg_upsert(con: AsyncConnection, data: T, data_type: type[T]):
    """Upsert a typed model instance."""
    return await pg_upsert_dict(con, data_type.get_table_name(), data.model_dump(), data_type.get_primary_key())


async def pg_upsert_many_dict(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: Sequence[dict],
    primary_keys: Sequence[str],
) -> None:
    """Batch upsert — one round-trip via executemany."""
    if not data:
        return
    fields = list(data[0])
    updates = [SQL("{col} = EXCLUDED.{col}").format(col=Identifier(k)) for k in fields if k not in primary_keys]
    query = SQL(
        "INSERT INTO {tbl} ({cols}) VALUES ({vals}) ON CONFLICT ({pks}) DO UPDATE SET {updates}"
    ).format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in fields),
        vals=SQL(", ").join(Placeholder(k) for k in fields),
        pks=SQL(", ").join(Identifier(pk) for pk in primary_keys),
        updates=SQL(", ").join(updates),
    )
    async with con.cursor() as cur:
        await cur.executemany(query, data)


async def pg_upsert_many(con: AsyncConnection, data: Sequence[T], data_type: type[T]) -> None:
    await pg_upsert_many_dict(con, data_type.get_table_name(), [d.model_dump() for d in data], data_type.get_primary_key())


async def pg_insert_many(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: Sequence[dict],
) -> None:
    """Batch insert — no RETURNING, one round-trip via executemany."""
    if not data:
        return
    fields = list(data[0])
    query = SQL("INSERT INTO {tbl} ({cols}) VALUES ({vals})").format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in fields),
        vals=SQL(", ").join(Placeholder(k) for k in fields),
    )
    async with con.cursor() as cur:
        await cur.executemany(query, data)


async def pg_delete_dict(con: AsyncConnection, table_name: tuple[str, str], data: dict) -> dict | None:
    """Delete by arbitrary key dict, returns the deleted row."""
    where_parts = [SQL("{col} = {val}").format(col=Identifier(k), val=Placeholder(k)) for k in data]
    query = SQL("DELETE FROM {tbl} WHERE {where} RETURNING *").format(
        tbl=Identifier(*table_name),
        where=SQL(" AND ").join(where_parts),
    )
    async with con.cursor() as cur:
        await cur.execute(query, data)
        row = await cur.fetchone()
        if row is None:
            return None
        assert cur.description is not None
        return dict(zip([c[0] for c in cur.description], row))


async def pg_delete(con: AsyncConnection, data: T, data_type: type[T]) -> T | None:
    """Delete a typed model instance by its primary key(s)."""
    pk_dict = {pk: getattr(data, pk) for pk in data_type.get_primary_key()}
    row = await pg_delete_dict(con, data_type.get_table_name(), pk_dict)
    return data_type.model_validate(row) if row else None
```

Use these for simple CRUD. For anything that needs a custom `WHERE` clause, a join, aggregation, or ordering — write a dedicated `.sql` file and a repository method.

---

## Loading SQL files

```python
# db/loader.py
from functools import lru_cache
from pathlib import Path

_QUERIES_ROOT = Path(__file__).parent / "queries"

@lru_cache(maxsize=None)
def load_sql(topic: str, name: str) -> str:
    """Return the SQL text for queries/<topic>/<name>.sql."""
    return (_QUERIES_ROOT / topic / f"{name}.sql").read_text()
```

Each file is read from disk once per process lifetime. Never embed SQL strings in Python.

---

## Named parameters — `%(name)s` style

psycopg named-parameter style with a `dict` argument:

```sql
-- db/queries/users/list_active_users.sql
select
    usr.id,
    usr.email,
    usr.display_name,
    usr.created_at,
from users as usr
where usr.is_active = true
order by usr.created_at desc
limit %(limit)s
```

```python
await cur.execute(load_sql("users", "list_active_users"), {"limit": 50})
```

Never mix positional `%s` and named `%(name)s`. Never build SQL with f-strings or `str.format()`.

---

## Pydantic models — `{topic}_models.py`

Query results that aren't full-table rows (joins, aggregations, partial selects) get their own plain `BaseModel`:

```python
# models/user_models.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from db.pg_base import PostgresTableModel

class UserRow(PostgresTableModel):
    """Full users table row — used with pg_* helpers."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    created_at: datetime

    @staticmethod
    def get_table_name() -> tuple[str, str]:
        return ("public", "users")

    @staticmethod
    def get_primary_key() -> Sequence[str]:
        return ["id"]

class UserSummary(BaseModel):
    """Partial result — doesn't map to a single table."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    display_name: str
```

---

## Repository pattern

Use `pg_*` helpers for simple CRUD. Write custom SQL + a repository method for anything else:

```python
# db/repositories/user_repository.py
from __future__ import annotations
from psycopg.rows import dict_row
from db.loader import load_sql
from db.connection import get_pg_connection
from db.postgres import pg_retrieve, pg_insert, pg_delete
from models.user_models import UserRow, UserSummary

class UserRepository:
    async def get_by_id(self, user_id: int) -> UserRow | None:
        async with get_pg_connection() as conn:
            return await pg_retrieve(conn, UserRow, {"id": user_id})

    async def list_active(self, limit: int = 100) -> list[UserSummary]:
        sql = load_sql("users", "list_active_users")
        async with get_pg_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, {"limit": limit})
                rows = await cur.fetchall()
        return [UserSummary.model_validate(r) for r in rows]

    async def delete(self, user: UserRow) -> UserRow | None:
        async with get_pg_connection() as conn:
            return await pg_delete(conn, user, UserRow)
```

---

## Dynamic SQL

Avoid dynamic SQL whenever possible — a static `.sql` file is always clearer. When column names or table names genuinely vary at runtime, check `pyproject.toml` (or the project's `[project] requires-python`) to determine which approach to use — decide at authoring time, not with a runtime `sys.version_info` check:

### Python 3.14+ — t-string templates

```python

column = "email"  # dynamic — comes from caller
query = t"SELECT {column:i} FROM users WHERE active = {active}"
await cur.execute(query)
```

### Python < 3.14 — `psycopg.sql`

```python
from psycopg import sql

column = "email"
query = sql.SQL("SELECT {col} FROM users WHERE active = %(active)s").format(
    col=sql.Identifier(column),
)
await cur.execute(query, {"active": True})
```

`sql.Identifier` quotes the identifier at the driver level — SQL injection via column/table names is impossible. The value (`%(active)s`) always stays as a bound parameter, never interpolated.

**Never** use f-strings or string concatenation for identifiers or values.

---

## SQL formatting with sqlfmt

```bash
uv add --dev shandy-sqlfmt[jinjafmt]
sqlfmt db/queries/          # format
sqlfmt --check db/queries/  # CI check
```

`pyproject.toml`:

```toml
[tool.sqlfmt]
line_length = 119
```

sqlfmt enforces lowercase keywords, trailing commas, and consistent indentation.

---

## Quick checklist

- [ ] Simple CRUD uses `pg_*` helpers; custom queries use `.sql` files
- [ ] No inline SQL strings in Python
- [ ] All parameters use `%(name)s` style with a dict argument
- [ ] SQL files formatted with `sqlfmt`
- [ ] Results mapped to a Pydantic model in `{topic}_models.py`
- [ ] Table-mapped models extend `PostgresTableModel`; partial results extend `BaseModel`
- [ ] Dynamic SQL uses t-strings (3.14+) or `psycopg.sql` — chosen at authoring time based on pyproject.toml
