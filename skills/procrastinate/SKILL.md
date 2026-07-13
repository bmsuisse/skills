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

Set `JOB_RUNNER_MODE=subprocess` locally to skip the DB/worker entirely — jobs run in a child process, stdout/stderr are captured to a temp file. Leave unset (defaults to `procrastinate`) in production.

`dispatch_job` returns a `JobHandle(mode, id)` — job_id in procrastinate mode, PID in subprocess mode.

- `get_job_status(handle, conn)` — subprocess: `"started"` / `"succeeded"` / `"failed"` from exit code; procrastinate: `JobInfo` from `procrastinate_jobs`
- `get_job_history(handle, conn)` — subprocess: stdout/stderr as `str`; procrastinate: `list[JobEvent]` from `procrastinate_events`

See [`references/job-dispatch.md`](references/job-dispatch.md) for full implementation of `job_dispatch.py`, `job_runner.py`, and the DB query helpers.

## Reference files

- [`references/job-dispatch.md`](references/job-dispatch.md) — dual-mode dispatch, `JobHandle`, subprocess log capture, DB query helpers
- [`references/connectors.md`](references/connectors.md) — DSN, connection pools, PgBouncer, sharing pool with postgres-best-practices
- [`references/schema.md`](references/schema.md) — applying initial schema and migrations via plain SQL
- [`references/azure-setup.md`](references/azure-setup.md) — Azure Web App & Container App start scripts
- [`references/advanced.md`](references/advanced.md) — retry strategies, periodic tasks, locks, queues
