---
name: postgres-best-practices
plugin: coding
description: >
  PostgreSQL coding standards for Python projects using psycopg (no ORM). Use
  this skill whenever the user is writing or reviewing code that queries
  PostgreSQL with psycopg, creates SQL files, maps query results to Python
  objects, or asks how to structure database access code. Triggers on things
  like "add a database query", "write a SQL query", "create a repository",
  "fetch from postgres", "insert into the database", "update the DB",
  "parameterized query", "pydantic model from DB row", "sql file", "dynamic
  SQL", or any mention of psycopg, psycopg2, asyncpg, or SQLAlchemy where the
  user seems open to a different approach. Also use when the user asks about
  connection pooling, transactions, cursor factories, or how to organise
  database code.
---

# PostgreSQL Best Practices (psycopg, no ORM)

Core rules for every piece of database code in this project:

- **No ORM** — use [psycopg](https://www.psycopg.org/psycopg3/) directly.
- **Inline SQL** — trivial queries of **4 lines or fewer** may be written inline in Python. Anything with JOINs, subqueries, CTEs, aggregations, or multiple conditions must live in its own `.sql` file.
- **Named parameters** — always `%(name)s` style, never positional `%s`.
- **SQL formatting** — all `.sql` files are formatted with [shandy-sqlfmt](https://sqlfmt.com/).
- **Dynamic SQL** — check `pyproject.toml` for the Python version; use psycopg t-string templates on 3.14+, otherwise `psycopg.sql`. See [references/dynamic-sql.md](references/dynamic-sql.md).
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

Inline SQL (acceptable — simple, ≤ 4 lines):

```python
await cur.execute("SELECT id, name FROM users WHERE id = %(id)s", {"id": user_id})
```

Not acceptable inline (use a `.sql` file): anything with a JOIN, subquery, CTE, aggregation, or multiple conditions.

---

## Connection & pool

Copy [`references/connection.py`](references/connection.py) to `db/connection.py`. Adjust `_PREFIX` to match the project (e.g. `APP_POSTGRES_`, `MDM_POSTGRES_`).

---

## Base model — `PostgresTableModel`

Models that map 1:1 to a DB table extend `PostgresTableModel`:

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

Models that represent partial results (joins, aggregations, partial selects) just extend `BaseModel` directly.

---

## Generic CRUD helpers — `db/postgres.py`

Copy [`references/postgres.py`](references/postgres.py) to `db/postgres.py`. It provides:

| Helper | Purpose |
|--------|---------|
| `pg_retrieve` | Fetch single row by PK |
| `pg_retrieve_many` | Fetch rows matching filter dict |
| `pg_insert` | Insert one row, `RETURNING *` |
| `pg_update` / `pg_update_dict` | Update by PK |
| `pg_upsert` / `pg_upsert_dict` | `INSERT … ON CONFLICT … DO UPDATE` |
| `pg_upsert_many` / `pg_upsert_many_dict` | Batch upsert via `executemany` |
| `pg_insert_many` | Batch insert via `executemany` |
| `pg_delete` / `pg_delete_dict` | Delete by PK, returns deleted row |

Use these for simple CRUD. For custom `WHERE` clauses, joins, aggregations, or ordering — write a dedicated `.sql` file and a repository method.

---

## Loading SQL files

Use this helper:

```python
# db/loader.py
from functools import lru_cache
from pathlib import Path
from typing import LiteralString, cast

_SQL_ROOT = Path(__file__).parent / "sql"

@lru_cache(maxsize=None)
def load_sql(topic: str, name: str) -> LiteralString:
    """Return the SQL text for sql/<topic>/<name>.sql."""
    return cast(LiteralString, (_SQL_ROOT / topic / f"{name}.sql").read_text())
```

---

## Named parameters — `%(name)s` style

```sql
-- db/queries/users/list_active_users.sql
select usr.id, usr.email, usr.display_name, usr.created_at
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

```python
# models/user_models.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from db.pg_base import PostgresTableModel

class UserRow(PostgresTableModel):
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
    model_config = ConfigDict(from_attributes=True)
    id: int
    display_name: str
```

---

## Repository pattern

```python
# db/repositories/user_repository.py
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

See [`references/dynamic-sql.md`](references/dynamic-sql.md) for full examples of t-strings (3.14+) and `psycopg.sql` (< 3.14), including format specifiers, dynamic identifiers, nested templates, and NOTIFY.

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

---

## Schema files & documentation

Table/view/function definitions themselves (the `CREATE TABLE` statements, `COMMENT ON` documentation, migrations) live in a `database/` folder in source — see [database-in-source](../database-in-source/SKILL.md) for that layout. This skill covers the *application* side: querying, mapping, and organising `db/` code that talks to those tables.

---

## Avoid LATERAL JOIN — use CTEs instead

`LATERAL JOIN` is hard to read and often poorly optimised. Prefer a CTE that pre-aggregates, then join it:

```sql
with latest_order as (
    select
        o.user_id,
        o.total,
        row_number() over (
            partition by o.user_id order by o.created_at desc
        ) as rn
    from orders as o
)
select u.id, u.email, lo.total
from users as u
join latest_order as lo on lo.user_id = u.id and lo.rn = 1
```

---

## Temporal tables

See [`references/temporal-tables.md`](references/temporal-tables.md) for the full setup — `sys_period tstzrange`, `CREATE TABLE … LIKE` history table, GiST index, trigger wiring, point-in-time query, and `set_system_time` backdating.

---

## Quick checklist

- [ ] Simple CRUD uses `pg_*` helpers; custom queries use `.sql` files
- [ ] Inline SQL only for trivial queries ≤ 4 lines; anything with JOINs/CTEs/aggregations/subqueries uses a `.sql` file
- [ ] All parameters use `%(name)s` style with a dict argument
- [ ] SQL files formatted with `sqlfmt`
- [ ] Results mapped to a Pydantic model in `{topic}_models.py`
- [ ] Table-mapped models extend `PostgresTableModel`; partial results extend `BaseModel`
- [ ] Dynamic SQL uses t-strings (3.14+) or `psycopg.sql` — chosen at authoring time based on pyproject.toml
- [ ] No `LATERAL JOIN` — use a CTE that groups/aggregates first, then join it
- [ ] Temporal tables use nearform/temporal_tables trigger; `sys_period tstzrange` on live table, mirror `_history` table with GiST index
- [ ] Schema files (tables, `COMMENT ON`, migrations) follow [database-in-source](../database-in-source/SKILL.md)
