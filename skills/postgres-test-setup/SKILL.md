---
name: postgres-test-setup
description: Set up and work with a local PostgreSQL test database in Docker for integration/e2e tests. Use this skill when the user wants to add, configure, or troubleshoot a local test Postgres instance, pytest database fixtures, SQL schema initialisation from files, or database schema changes. Triggers on requests like "set up a test database", "add postgres fixtures", "init test DB", "local postgres for tests", "add a column", "create a table", "change the schema", or anything involving the local test Postgres database.
---

# Postgres Test Setup

Spins up a **Docker-based PostgreSQL** instance, applies all SQL schema files from a `database/` directory in dependency order, and seeds it with test data from `.test_data.json` sidecar files.

---

## Quick start

### 1. Copy the script

Place [`scripts/start_postgres.py`](scripts/start_postgres.py) at `test_server/start_postgres.py` in the project.

Adjust the two constants at the top of the file:

```python
DOCKER_IMAGE = "pgvector/pgvector:pg18-trixie" # or "postgres:17" without pgvector
DATABASE_DIR = "database"                       # folder with .sql files (relative to cwd)
```

`ENV_PREFIX` is **auto-detected** from `[tool.pytest_env]` in `pyproject.toml` by scanning for a key ending in `POSTGRES_HOST` (e.g. `MDM_POSTGRES_HOST` → prefix `MDM_`). Falls back to `TEST_` if no match is found or the file is absent. No manual change needed once `pyproject.toml` is configured.

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

## Making database changes

**All schema changes live in SQL files. Never alter the production or shared database directly.**

### Rules

1. **Edit the `.sql` file** in `database/` — that is the source of truth.
2. **Test the change on the local test DB only** using `run_sql.py` (see below).
3. Never run `ALTER`, `DROP`, or `CREATE` against any database whose `TEST_POSTGRES_HOST` is not `localhost`.
4. After verifying, a human applies the same SQL to production as a migration.

### Workflow for a schema change

```
1. Edit / create the relevant .sql file in database/
2. Run the file against the local test DB to verify it works:
       uv run test_server/run_sql.py database/path/to/file.sql
3. If the change is destructive (DROP, ALTER) and needs a clean slate:
       uv run -m test_server.start_postgres --force-reset-db
4. Run the tests to confirm nothing broke.
```

### Adding a new table

1. Create `database/<schema>/tables/<table_name>.sql`.
2. Optionally create `database/<schema>/tables/<table_name>.test_data.json` with seed rows.
3. Run `uv run -m test_server.start_postgres` — the new file is picked up automatically.

### Modifying an existing table

- **Additive change** (new nullable column, new index): edit the `.sql` file and apply the matching `ALTER TABLE` via `run_sql.py`. The live test DB is updated without a full reset.
- **Breaking change** (rename column, change type, drop column): edit the `.sql` file, then do a full reset:
  `uv run -m test_server.start_postgres --force-reset-db`

---

## Executing SQL on the test database

Copy [`scripts/run_sql.py`](scripts/run_sql.py) to `test_server/run_sql.py`.

The script auto-detects the env-var prefix from `pyproject.toml` (same logic as `start_postgres.py`) and **refuses to run if `<PREFIX>POSTGRES_HOST` is not `localhost`**.

### Run a SQL file

```bash
uv run test_server/run_sql.py database/1_dim/tables/user.sql
```

### Run inline SQL

```bash
uv run test_server/run_sql.py --sql "SELECT * FROM dim.user LIMIT 10"
```

### Run inline SQL and print results

```bash
uv run test_server/run_sql.py --sql "SELECT id, name FROM dim.user" --results
```

Results are printed as an ASCII table:
```
+----+-------+
| id | name  |
+----+-------+
| 1  | Alice |
| 2  | Bob   |
+----+-------+
(2 rows)
```

### When to use `run_sql.py`

| Task | Command |
|------|---------|
| Apply an additive migration to the live test DB | `run_sql.py database/.../alter.sql` |
| Spot-check data after a change | `run_sql.py --sql "SELECT ..." --results` |
| Re-apply a single function/view after editing it | `run_sql.py database/.../my_function.sql` |
| Quick schema inspection | `run_sql.py --sql "\\d dim.user" --results` |

> **Never** use `run_sql.py` to apply changes to production. It is locked to `localhost` by design.

---

## Database directory layout

The script walks `database/` and executes `.sql` files in this order:

| Priority | Directory/filename pattern | Object type        |
|----------|----------------------------|--------------------|
| 1        | `schema`                   | `CREATE SCHEMA`    |
| 2        | `types`                    | Custom types/enums |
| 3        | `tables`                   | Tables             |
| 4        | `scalar_functions`         | Scalar functions   |
| 5        | `functions`                | Functions          |
| 6        | `views`                    | Views              |
| 7        | `table_functions`          | Table functions    |
| 8        | `procedures`               | Procedures         |
| 100      | `permissions`              | Grants             |
| 101      | `indexes`                  | Indexes            |

Files named `all.sql`, `100_permissions.sql`, or containing `.prod` are skipped. Migrations folders are skipped.

Cross-file foreign key dependencies are resolved automatically via `sqlglot` — delayed files are retried until all deps are met.

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

Place a `.test_data.json` file next to any table `.sql` file. It must be a JSON array of row objects:

```json
[
  {"id": 1, "name": "Alice", "role": "admin"},
  {"id": 2, "name": "Bob",   "role": "reader"}
]
```

- Nested dicts/lists are automatically serialised to JSON strings (suitable for `jsonb` columns).
- Rows are deleted before re-insertion on each `--force-reset-db` run.
- On a normal run, a table is skipped if its row count already matches the JSON file.

---

## Environment variables reference

| Variable                  | Default    | Description                        |
|---------------------------|------------|------------------------------------|
| `TEST_POSTGRES_HOST`      | `localhost` | Postgres host                     |
| `TEST_POSTGRES_PORT`      | `54324`     | Host port (avoids conflict w/ 5432)|
| `TEST_POSTGRES_DB`        | `app_test`  | Database name                     |
| `TEST_POSTGRES_USER`      | `postgres`  | Superuser                         |
| `TEST_POSTGRES_PASSWORD`  | `testpwd`   | Password                          |
| `SKIP_START_POSTGRES`     | —           | Set to `1` to skip Docker startup (e.g. CI service containers) |

---

## CI / GitHub Actions

Skip the Docker startup and point at a service container instead:

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

The included script handles simple columns and JSONB. If the project uses **PostgreSQL composite types or custom enums** that need psycopg adaptation (e.g. via `psycopg.adapt`), extend `insert_test_data` with a helper that registers the types before inserting. In the original MDMApp project this was done via a `ComplexHelper` class — port that pattern here if needed.
