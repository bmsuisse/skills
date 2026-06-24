---
name: procrastinate
description: >
  PostgreSQL-based async task queue for Python using Procrastinate. Use this skill whenever the user is working with Procrastinate — setting it up, defining tasks, deferring jobs, running workers, configuring retries, periodic tasks, or deploying to Azure (Web App or Container App). Also triggers on: "background jobs", "task queue postgres", "deferred task", "async worker", "procrastinate worker", "procrastinate app", "run worker in azure", "start script worker", "background task fastapi", "background task django procrastinate".
---

# Procrastinate — PostgreSQL Task Queue

Procrastinate is an async Python task queue that uses PostgreSQL as its broker — no Redis/RabbitMQ needed. Jobs are stored in the DB and workers pick them up via `LISTEN/NOTIFY`.

**Docs:** https://procrastinate.readthedocs.io/en/stable/

## Quick decisions

| Situation | Recommendation |
|---|---|
| FastAPI / async | Use `PsycopgConnector`, run worker via lifespan |
| Azure Web App | See [`references/azure-setup.md`](references/azure-setup.md) |
| Azure Container App | See [`references/azure-setup.md`](references/azure-setup.md) |
| Retry / periodic tasks | See [`references/advanced.md`](references/advanced.md) |

## Install

```bash
pip install procrastinate          # base
pip install 'procrastinate[django]'  # Django
```

## App setup

```python
# myapp/procrastinate_app.py  ← keep in a non-__main__ module
import procrastinate

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector()  # reads PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD
)
```

> For DSN, pool tuning, PgBouncer, or sharing a pool with `postgres-best-practices` see [`references/connectors.md`](references/connectors.md).

## Apply DB schema (once per environment)

Get the SQL and apply it yourself — no CLI wrapper needed:

```bash
# Dump the full initial schema SQL
procrastinate schema --print-schema | psql $DATABASE_URL

# Or apply a specific migration
cat $(procrastinate schema --migrations-path)/02.00.00_01_pre_some_migration.sql | psql $DATABASE_URL
```

Migration files are plain `.sql` — use `psql`, pgAdmin, or your existing migration tooling (Flyway, sqitch, etc.). See [`references/schema.md`](references/schema.md) for the migration naming convention and upgrade workflow.

## Define & defer a task

```python
@app.task(queue="default", retry=3)
async def send_email(to: str, subject: str):
    ...

# Defer (schedule) a job from anywhere
await send_email.defer_async(to="user@example.com", subject="Hi")
# Sync variant
send_email.defer(to="user@example.com", subject="Hi")
```

## Run a worker

```bash
# CLI (recommended for production/Azure)
procrastinate --app=myapp.procrastinate_app.app worker --concurrency=10

# Python — inside FastAPI lifespan, etc.
await app.run_worker_async(concurrency=10, install_signal_handlers=False)
```

## Dual-mode dispatch (procrastinate vs subprocess)

For easier local debugging, wrap job dispatch behind a `JOB_RUNNER_MODE` env var so you can run tasks as a plain subprocess instead of going through Procrastinate.

### `myapp/job_dispatch.py`

```python
import asyncio
import importlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_MODE = os.getenv("JOB_RUNNER_MODE", "procrastinate")  # "procrastinate" | "subprocess"

# pid -> log file path; only populated in subprocess mode
_subprocess_logs: dict[int, Path] = {}


@dataclass
class JobHandle:
    mode: str  # "procrastinate" | "subprocess"
    id: int    # procrastinate job_id  OR  subprocess PID


async def dispatch_job(job_name: str, module: str, **kwargs) -> JobHandle:
    if _MODE == "subprocess":
        log_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=".log", prefix=f"job_{job_name}_"
        )
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "myapp.job_runner",
            module, job_name, json.dumps(kwargs),
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
        )
        log_file.close()
        _subprocess_logs[proc.pid] = Path(log_file.name)
        # fire and forget — do not await proc.wait()
        return JobHandle(mode="subprocess", id=proc.pid)
    else:
        mod = importlib.import_module(module)
        task = getattr(mod, job_name)
        job_id: int = await task.defer_async(**kwargs)
        return JobHandle(mode="procrastinate", id=job_id)


def get_subprocess_logs(handle: JobHandle) -> str:
    """Read captured stdout/stderr for a subprocess-mode job. Returns '' if not found."""
    if handle.mode != "subprocess":
        raise ValueError("get_subprocess_logs only applies to subprocess mode")
    log_path = _subprocess_logs.get(handle.id)
    if log_path is None or not log_path.exists():
        return ""
    return log_path.read_text()
```

> **Note:** `_subprocess_logs` is in-memory — logs are only available within the same process lifetime. Log files accumulate in the system temp directory; clean them up as needed.

### `myapp/job_runner.py`

```python
import asyncio
import importlib
import json
import sys


async def _run(module: str, job_name: str, kwargs: dict) -> None:
    mod = importlib.import_module(module)
    func = getattr(mod, job_name)
    await func(**kwargs)


if __name__ == "__main__":
    module, job_name, kwargs_json = sys.argv[1], sys.argv[2], sys.argv[3]
    asyncio.run(_run(module, job_name, json.loads(kwargs_json)))
```

### Querying job status and history (procrastinate mode)

Use these against `procrastinate_jobs` and `procrastinate_events` (see schema below). Pass a psycopg `AsyncConnection` or compatible cursor.

```python
from dataclasses import dataclass
from datetime import datetime

import psycopg


@dataclass
class JobInfo:
    id: int
    task_name: str
    queue_name: str
    status: str
    attempts: int
    args: dict
    scheduled_at: datetime | None


@dataclass
class JobEvent:
    type: str
    at: datetime | None


async def get_job_status(conn: psycopg.AsyncConnection, handle: JobHandle) -> JobInfo | None:
    if handle.mode != "procrastinate":
        raise ValueError("get_job_status only applies to procrastinate mode")
    async with conn.cursor(row_factory=psycopg.rows.class_row(JobInfo)) as cur:
        await cur.execute(
            """
            SELECT id, task_name, queue_name, status, attempts, args, scheduled_at
            FROM procrastinate_jobs
            WHERE id = %s
            """,
            (handle.id,),
        )
        return await cur.fetchone()


async def get_job_history(conn: psycopg.AsyncConnection, handle: JobHandle) -> list[JobEvent]:
    """Returns lifecycle events: deferred → started → succeeded/failed/retried/..."""
    if handle.mode != "procrastinate":
        raise ValueError("get_job_history only applies to procrastinate mode")
    async with conn.cursor(row_factory=psycopg.rows.class_row(JobEvent)) as cur:
        await cur.execute(
            """
            SELECT type, at
            FROM procrastinate_events
            WHERE job_id = %s
            ORDER BY at
            """,
            (handle.id,),
        )
        return await cur.fetchall()
```

### `procrastinate_events.type` values

| Event | Meaning |
|---|---|
| `deferred` | Job created in `todo` |
| `started` | Worker picked it up |
| `succeeded` | Finished without error |
| `failed` | Raised an exception |
| `deferred_for_retry` | Being retried, back to `todo` |
| `retried` | Manually retried |
| `cancelled` | Cancelled before pickup |
| `aborted` | Aborted while running |

### Usage

```python
# instead of: await send_email.defer_async(to="user@example.com", subject="Hi")
handle = await dispatch_job("send_email", "myapp.tasks.email", to="user@example.com", subject="Hi")

# subprocess mode — read captured stdout/stderr
if handle.mode == "subprocess":
    print(get_subprocess_logs(handle))

# procrastinate mode — check DB
if handle.mode == "procrastinate":
    info = await get_job_status(conn, handle)
    events = await get_job_history(conn, handle)
```

Set `JOB_RUNNER_MODE=subprocess` locally to skip the DB/worker entirely — the task function runs directly in a child process. Leave it unset (or set to `procrastinate`) in production.

## Reference files

- [`references/connectors.md`](references/connectors.md) — DSN, connection pools, PgBouncer, sharing pool with postgres-best-practices
- [`references/schema.md`](references/schema.md) — applying initial schema and migrations via plain SQL
- [`references/azure-setup.md`](references/azure-setup.md) — Azure Web App & Container App start scripts
- [`references/advanced.md`](references/advanced.md) — retry strategies, periodic tasks, locks, queues
