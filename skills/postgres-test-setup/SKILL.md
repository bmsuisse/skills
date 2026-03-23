---
name: postgres-test-setup
description: >
  Set up and work with a local PostgreSQL test database in Docker for
  integration/e2e tests. Use this skill whenever the user wants to add,
  configure, troubleshoot, or run queries against a local test Postgres
  instance — even if they don't say "postgres" explicitly. Triggers on things
  like "set up a test database", "add postgres fixtures", "init test DB",
  "local postgres for tests", "add a column", "create a table", "change the
  schema", "run a SQL query on my test DB", "reset the database", "database is
  out of sync", "test data", or anything involving the local test Postgres
  database. Also use this skill when the user asks how to inspect the test DB,
  seed rows, or apply a migration to the local environment.
---

# Postgres Test Setup

Spins up a **Docker-based PostgreSQL** instance, applies all SQL schema files from a `database/` directory in dependency order, and seeds test data from `.test_data.json` sidecar files.

---

## Quick reference

| What do you need? | Command |
|---|---|
| First-time setup | Follow steps 1–5 below |
| Add a new table | Create `.sql` + optional `.test_data.json`, then `uv run -m test_server.start_postgres` |
| Additive change (new column/index) | Edit `.sql`, apply via `run_sql.py`, no reset needed |
| Breaking change (rename/drop column) | Edit `.sql`, then `uv run -m test_server.start_postgres --force-reset-db` |
| Inspect test DB data | `uv run test_server/run_sql.py --sql "SELECT ..." --results` |
| Re-apply a function/view | `uv run test_server/run_sql.py database/path/to/file.sql` |
| Reset to clean slate | `uv run -m test_server.start_postgres --force-reset-db` |

---

## Initial setup

### 1. Copy the scripts

Place [`scripts/start_postgres.py`](scripts/start_postgres.py) at `test_server/start_postgres.py` and [`scripts/run_sql.py`](scripts/run_sql.py) at `test_server/run_sql.py` in the project.

Adjust the two constants at the top of `start_postgres.py`:

```python
DOCKER_IMAGE = "pgvector/pgvector:pg18-trixie"  # or "postgres:17" without pgvector
DATABASE_DIR = "database"                        # folder with .sql files (relative to cwd)
```

`ENV_PREFIX` is **auto-detected** from `[tool.pytest_env]` in `pyproject.toml` by scanning for a key ending in `POSTGRES_HOST` (e.g. `MDM_POSTGRES_HOST` → prefix `MDM_`). Falls back to `TEST_` if no match is found.

### 2. Add pytest dependencies

```bash
uv add --dev psycopg[binary] sqlglot docker pytest pytest-asyncio pytest-env
# if using pgvector:
uv add --dev pgvector
```

### 3. Configure pytest environment variables

In `pyproject.toml`:

```toml
[tool.pytest_env]
TEST_POSTGRES_PASSWORD = "testpwd"
TEST_POSTGRES_DB       = "app_test"
TEST_POSTGRES_USER     = "postgres"
TEST_POSTGRES_PORT     = "54324"
TEST_POSTGRES_HOST     = "localhost"
```

### 4. Add a session-scoped pytest fixture

In `tests/conftest.py`:

```python
import os
import pytest_asyncio
from test_server.start_postgres import postgres_test_env, setup_database, start_postgres

@pytest_asyncio.fixture(scope="session", autouse=True)
async def ensure_test_postgres_server():
    for key, value in postgres_test_env.items():
        os.environ[key] = value
    start_postgres()
    await setup_database(force_reset_db=False)
    yield
```

### 5. Run manually (first-time or reset)

```bash
# Normal init (idempotent — skips tables already populated)
uv run -m test_server.start_postgres

# Full reset — drops and recreates the DB, re-inserts all test data
uv run -m test_server.start_postgres --force-reset-db
```

---

## Making schema changes

**All schema changes live in SQL files. Never alter the production or shared database directly.**

### When to reset vs. apply incrementally

| Change type | Approach |
|---|---|
| New table or view | `uv run -m test_server.start_postgres` (picks up new files automatically) |
| New nullable column, new index | Edit `.sql`, apply via `run_sql.py`, no reset needed |
| Rename column, change type, drop column | Edit `.sql`, then run `--force-reset-db` |

### Workflow

```
1. Edit / create the relevant .sql file in database/
2. Apply to the local test DB:
   - Additive:  uv run test_server/run_sql.py database/path/to/file.sql
   - Breaking:  uv run -m test_server.start_postgres --force-reset-db
3. Run the tests to confirm nothing broke.
```

After verifying locally, a human applies the same SQL to production as a migration.

### Adding a new table

1. Create `database/<schema>/tables/<table_name>.sql`.
2. Optionally create `database/<schema>/tables/<table_name>.test_data.json` with seed rows.
3. Run `uv run -m test_server.start_postgres` — the new file is picked up automatically.

---

## Executing SQL on the test database

`run_sql.py` auto-detects the env-var prefix from `pyproject.toml` and **refuses to run if `<PREFIX>POSTGRES_HOST` is not `localhost`**.

```bash
# Run a SQL file
uv run test_server/run_sql.py database/1_dim/tables/user.sql

# Run inline SQL
uv run test_server/run_sql.py --sql "SELECT * FROM dim.user LIMIT 10"

# Run inline SQL and print results as an ASCII table
uv run test_server/run_sql.py --sql "SELECT id, name FROM dim.user" --results
```

Results look like:
```
+----+-------+
| id | name  |
+----+-------+
| 1  | Alice |
| 2  | Bob   |
+----+-------+
(2 rows)
```

**Never** use `run_sql.py` to apply changes to production — it is locked to `localhost` by design.

---

## Database directory layout

The script walks `database/` and executes `.sql` files in this order:

| Priority | Directory/filename pattern | Object type |
|---|---|---|
| 1 | `schema` | `CREATE SCHEMA` |
| 2 | `types` | Custom types/enums |
| 3 | `tables` | Tables |
| 4 | `scalar_functions` | Scalar functions |
| 5 | `functions` | Functions |
| 6 | `views` | Views |
| 7 | `table_functions` | Table functions |
| 8 | `procedures` | Procedures |
| 100 | `permissions` | Grants |
| 101 | `indexes` | Indexes |

Files named `all.sql`, `100_permissions.sql`, or containing `.prod` are skipped. Migration folders are skipped.

Cross-file foreign key dependencies are resolved automatically via `sqlglot`.

**Recommended structure:**

```
database/
├── 1_schema.sql
├── 0_public/
│   └── types/
│       └── my_enum.sql
├── 1_dim/
│   └── tables/
│       ├── user.sql
│       └── user.test_data.json      ← auto-loaded after user.sql
└── 100_permissions.sql              ← skipped by default
```

---

## Test data files

Place a `.test_data.json` file next to any table `.sql` file — a JSON array of row objects:

```json
[
  {"id": 1, "name": "Alice", "role": "admin"},
  {"id": 2, "name": "Bob",   "role": "reader"}
]
```

- Nested dicts/lists are automatically serialised to JSON strings (for `jsonb` columns).
- On `--force-reset-db`, rows are deleted and re-inserted.
- On a normal run, a table is skipped if its row count already matches the JSON file.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TEST_POSTGRES_HOST` | `localhost` | Postgres host |
| `TEST_POSTGRES_PORT` | `54324` | Host port (avoids conflict with 5432) |
| `TEST_POSTGRES_DB` | `app_test` | Database name |
| `TEST_POSTGRES_USER` | `postgres` | Superuser |
| `TEST_POSTGRES_PASSWORD` | `testpwd` | Password |
| `SKIP_START_POSTGRES` | — | Set to `1` to skip Docker startup (e.g. CI service containers) |

---

## CI / GitHub Actions

Skip Docker startup and point at a service container instead:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg18-trixie
    env:
      POSTGRES_PASSWORD: testpwd
      POSTGRES_DB: app_test
      POSTGRES_USER: postgres
    ports:
      - 54324:5432

env:
  SKIP_START_POSTGRES: "1"
  TEST_POSTGRES_HOST: localhost
  TEST_POSTGRES_PORT: "54324"
  TEST_POSTGRES_DB: app_test
  TEST_POSTGRES_USER: postgres
  TEST_POSTGRES_PASSWORD: testpwd
```

---

## Adapting for complex Postgres types

The included script handles simple columns and JSONB. If the project uses **PostgreSQL composite types or custom enums** that need psycopg adaptation, use the `ComplexHelper` class in [`references/complex_helper.py`](references/complex_helper.py). Read that file for the full implementation and usage instructions — it shows how to extend `insert_test_data` to register custom types before inserting.
