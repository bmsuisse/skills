# Advanced Features

## Retry strategies

```python
# Simple: retry N times
@app.task(retry=5)
async def flaky_task(): ...

# Retry indefinitely
@app.task(retry=True)
async def always_retry(): ...

# Advanced: backoff, specific exceptions
import procrastinate

@app.task(retry=procrastinate.RetryStrategy(
    max_attempts=10,
    exponential_wait=5,          # 5s, 25s, 125s ...
    retry_exceptions={ConnectionError, IOError},
))
async def my_task(): ...
```

`RetryStrategy` wait options (pick one): `wait=N` (constant), `linear_wait=N`, `exponential_wait=N`.

## Periodic tasks (cron)

```python
@app.periodic(cron="*/5 * * * *")   # every 5 minutes
@app.task
async def run_healthchecks(timestamp: int): ...

@app.periodic(cron="0 * * * *")     # top of every hour
@app.task
async def cleanup(timestamp: int): ...
```

`timestamp` is the Unix time the task was scheduled for. Workers handle periodic scheduling — as long as one worker is up, tasks fire.

## Queues

Assign tasks to named queues and run workers scoped to specific queues:

```python
@app.task(queue="emails")
async def send_email(...): ...

@app.task(queue="reports")
async def generate_report(...): ...
```

```bash
# Worker only processes the "emails" queue
procrastinate worker --queue emails --concurrency=20
```

## Job locks (sequential execution)

Prevent two jobs with the same lock from running simultaneously:

```python
await send_email.defer_async(to="user@example.com", lock="user:42")
```

## Queueing locks (prevent accumulation)

If a job with the same queueing lock is already queued, skip enqueueing:

```python
await refresh_cache.defer_async(queueing_lock="cache-refresh")
```

## Schedule in the future

```python
from datetime import timedelta

await send_email.defer_async(
    to="user@example.com",
    schedule_in={"hours": 2},   # or schedule_at=<datetime>
)
```

## Concurrency

```bash
procrastinate worker --concurrency=30
```

Each worker can run N async jobs concurrently (I/O-bound tasks benefit most). For CPU-bound work, run multiple worker processes instead.
