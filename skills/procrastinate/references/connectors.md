# Connectors

Use `PsycopgConnector` (async) for all apps — it's required to run the worker.

## Three ways to specify the connection

**1. Environment variables (recommended for Azure / containers)**

```python
app = procrastinate.App(connector=procrastinate.PsycopgConnector())
```

Set `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` in the environment.
Azure Database for PostgreSQL connection string maps to these directly.

**2. DSN / conninfo**

```python
app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo="postgresql://user:pass@host:5432/dbname"
    )
)
```

**3. Keyword arguments**

```python
app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        kwargs={"host": "...", "dbname": "...", "user": "...", "password": "..."}
    )
)
```

## Connection pool tuning

Pass any `psycopg_pool.AsyncConnectionPool` kwargs:

```python
procrastinate.PsycopgConnector(
    conninfo="...",
    min_size=2,
    max_size=10,
)
```

## Sharing a pool with postgres-best-practices

If the project uses the `postgres-best-practices` skill, it already has an `AsyncConnectionPool` in `db/connection.py`. Pass it to the procrastinate connector so both share one pool instead of opening two:

```python
# db/connection.py (postgres-best-practices pattern)
from psycopg_pool import AsyncConnectionPool
_pool: AsyncConnectionPool | None = None

async def open_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(conninfo=_dsn(), open=False, ...)
    await _pool.open()

# myapp/procrastinate_app.py
import procrastinate
from db.connection import _pool

app = procrastinate.App(connector=procrastinate.PsycopgConnector())

# In your app startup (e.g. FastAPI lifespan / Django AppConfig.ready):
async def startup():
    await open_pool()
    await app.connector.open_async(pool=_pool)  # share the pool

async def shutdown():
    await app.connector.close_async()
    await _pool.close()  # or app.connector.close_async() covers it if procrastinate owns close
```

This way procrastinate piggybacks on the existing pool. Size the pool (`max_size`) to account for both app queries and worker concurrency.

---

## PgBouncer (transaction pooling)

Use `AsyncNullConnectionPool` to bypass the built-in pool:

```python
import psycopg_pool

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        pool_factory=psycopg_pool.AsyncNullConnectionPool,
        conninfo="...",
    )
)
```
