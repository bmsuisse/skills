# Dynamic SQL

Avoid dynamic SQL whenever possible — a static `.sql` file is always clearer. When column or table names genuinely vary at runtime, check `pyproject.toml` (or `[project] requires-python`) to pick an approach at authoring time, not with a runtime `sys.version_info` check.

---

## Python 3.14+ — t-string templates

T-strings look like f-strings but are evaluated by psycopg — values are always sent as bound parameters, never interpolated.

**Format specifiers:**

| Specifier | Meaning |
|-----------|---------|
| `{val}` / `{val:s}` | Bound parameter, automatic format (default) |
| `{val:b}` | Bound parameter, binary format |
| `{val:t}` | Bound parameter, text format |
| `{name:i}` | SQL identifier (table/column name) — double-quoted |
| `{val:l}` | Literal value merged client-side (use sparingly) |
| `{snippet:q}` | SQL snippet — another t-string or `sql.SQL`/`Composed` instance |

**Basic parameter:**

```python
await cur.execute(t"SELECT * FROM users WHERE id = {user_id}")
```

**Dynamic identifier (`:i`):**

```python
column = "email"
await cur.execute(t"SELECT {column:i} FROM users WHERE active = {active}")
```

**NOTIFY — requires client-side composition (`:i` and `:l`):**

```python
def send_notify(conn: Connection, channel: str, payload: str) -> None:
    conn.execute(t"NOTIFY {channel:i}, {payload:l}")
```

**Nested templates with `:q` (dynamic WHERE clause):**

```python
from psycopg import sql

def search_users(
    conn: Connection,
    ids: Sequence[int] | None = None,
    name_pattern: str | None = None,
) -> list[UserRow]:
    filters = []
    if ids is not None:
        filters.append(t"u.id = ANY({list(ids)})")
    if name_pattern is not None:
        filters.append(t"u.name ~* {name_pattern}")
    if not filters:
        raise TypeError("at least one filter required")
    joined = sql.SQL(" AND ").join(filters)
    cur = conn.cursor(row_factory=class_row(UserRow))
    cur.execute(t"SELECT * FROM users AS u WHERE {joined:q}")
    return cur.fetchall()
```

**Inspect composed SQL without executing:**

```python
from psycopg import sql

name = "O'Reilly"
dob = datetime.date(1970, 1, 1)
print(sql.as_string(t"INSERT INTO tbl VALUES ({name}, {dob})"))
# INSERT INTO tbl VALUES ('O''Reilly', '1970-01-01'::date)
```

---

## Python < 3.14 — `psycopg.sql`

```python
from psycopg import sql

column = "email"
query = sql.SQL("SELECT {col} FROM users WHERE active = %(active)s").format(
    col=sql.Identifier(column),
)
await cur.execute(query, {"active": True})
```

`sql.Identifier` quotes the identifier at the driver level — SQL injection via column/table names is impossible. Values always stay as bound parameters.

**Never** use f-strings or string concatenation for identifiers or values.
