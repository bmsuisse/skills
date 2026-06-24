# Dual-mode job dispatch

Wrap job dispatch behind `JOB_RUNNER_MODE` so you can run tasks as a plain subprocess locally instead of going through Procrastinate.

| `JOB_RUNNER_MODE` | Behaviour |
|---|---|
| `procrastinate` (default) | defers via `task.defer_async()`, returns DB job id |
| `subprocess` | spawns `python -m myapp.job_runner`, returns PID |

## `myapp/job_dispatch.py`

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

# pid -> (process, log_path); only populated in subprocess mode
_subprocess_jobs: dict[int, tuple[asyncio.subprocess.Process, Path]] = {}


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
        _subprocess_jobs[proc.pid] = (proc, Path(log_file.name))
        # fire and forget — do not await proc.wait()
        return JobHandle(mode="subprocess", id=proc.pid)
    else:
        mod = importlib.import_module(module)
        task = getattr(mod, job_name)
        job_id: int = await task.defer_async(**kwargs)
        return JobHandle(mode="procrastinate", id=job_id)


def get_job_status(handle: JobHandle) -> str:
    """
    subprocess mode: "started" if still running, "succeeded" / "failed" by exit code.
    procrastinate mode: use get_job_status_db() instead.
    """
    if handle.mode != "subprocess":
        raise ValueError("get_job_status only applies to subprocess mode; use get_job_status_db for procrastinate")
    entry = _subprocess_jobs.get(handle.id)
    if entry is None:
        return "unknown"
    proc, _ = entry
    if proc.returncode is None:
        return "started"
    return "succeeded" if proc.returncode == 0 else "failed"


def get_job_history(handle: JobHandle) -> str:
    """
    subprocess mode: returns captured stdout/stderr as a string.
    procrastinate mode: use get_job_history_db() instead.
    """
    if handle.mode != "subprocess":
        raise ValueError("get_job_history only applies to subprocess mode; use get_job_history_db for procrastinate")
    entry = _subprocess_jobs.get(handle.id)
    if entry is None:
        return ""
    _, log_path = entry
    if not log_path.exists():
        return ""
    return log_path.read_text()
```

> `_subprocess_jobs` is in-memory — only available within the same process lifetime. Log files in the system temp dir accumulate; clean them up as needed.

## `myapp/job_runner.py`

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

## DB queries (procrastinate mode)

Pass a psycopg `AsyncConnection`.

```python
from dataclasses import dataclass
from datetime import datetime

import psycopg
import psycopg.rows


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


async def get_job_status_db(conn: psycopg.AsyncConnection, handle: JobHandle) -> JobInfo | None:
    if handle.mode != "procrastinate":
        raise ValueError("use get_job_status() for subprocess mode")
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


async def get_job_history_db(conn: psycopg.AsyncConnection, handle: JobHandle) -> list[JobEvent]:
    """Returns lifecycle events ordered by time: deferred → started → succeeded/failed/..."""
    if handle.mode != "procrastinate":
        raise ValueError("use get_job_history() for subprocess mode")
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

## Usage

```python
handle = await dispatch_job("send_email", "myapp.tasks.email", to="user@example.com", subject="Hi")

if handle.mode == "subprocess":
    print(get_job_status(handle))   # "started" | "succeeded" | "failed"
    print(get_job_history(handle))  # stdout/stderr as string

if handle.mode == "procrastinate":
    info = await get_job_status_db(conn, handle)
    events = await get_job_history_db(conn, handle)
```
