---
name: aiochannel-python
description: >
  Correct patterns for channel-based asyncio concurrency in Python using the aiochannel library.
  Use this skill whenever the user is working with aiochannel, writing producer/consumer pipelines
  in asyncio, or asking how to pass data between async tasks without a shared queue. Trigger on
  any mention of aiochannel, Channel[T], async producer/consumer, pipeline stages in asyncio,
  or "how do I pass items between coroutines". Also trigger when the user is about to write a
  producer that feeds a consumer task — even if they don't name aiochannel explicitly.
---

# aiochannel — Correct Usage Patterns

```python
from aiochannel import Channel, ChannelClosed, ChannelEmpty
```

`Channel[T]` is a typed, closeable async queue inspired by Go channels. Unlike `asyncio.Queue`,
a channel signals completion by being **closed AND drained** — this is the key design difference
that shapes every pattern below.

---

## Core API

| Method | Behaviour |
|--------|-----------|
| `Channel[T](maxsize=0)` | Create channel; maxsize=0 is unbounded |
| `await ch.put(item)` | Block until space; raises `ChannelClosed` if closed |
| `await ch.get()` | Block until item available; raises when closed+empty |
| `ch.close()` | Mark closed; consumers drain remaining items then stop |
| `ch.closed()` | `True` once closed |
| `ch.empty()` | `True` when no items buffered |
| `ch.put_nowait(item)` | Raises `ChannelFull` or `ChannelClosed` |
| `ch.get_nowait()` | Raises `ChannelEmpty` or `ChannelClosed` |
| `async for item in ch:` | Iterate until closed and empty (preferred) |

---

## Pattern 1 — Single producer: always close in `finally`

The producer **must** close the channel even if it raises. If it doesn't, the consumer will block
forever waiting for more items that will never come.

```python
async def producer(ch: Channel[int]) -> None:
    try:
        for i in range(10):
            await ch.put(i)
    finally:
        ch.close()  # guaranteed even on exception
```

```python
async def consumer(ch: Channel[int]) -> None:
    async for item in ch:  # exits cleanly when ch is closed+empty
        await process(item)
```

```python
ch: Channel[int] = Channel()
producer_task = asyncio.create_task(producer(ch))
consumer_task = asyncio.create_task(consumer(ch))
await producer_task
await consumer_task
```

---

## Pattern 2 — Multiple producers: gather + close in a wrapper

When several coroutines all write to the same channel, **only one thing should close it** — after
all producers are done. The idiom is a wrapper coroutine that gathers all producers and closes in
its own `finally`:

```python
# Individual producers do NOT close the channel
async def producer_a(ch: Channel[int]) -> None:
    for i in range(5):
        await ch.put(i)

async def producer_b(ch: Channel[int]) -> None:
    for i in range(5, 10):
        await ch.put(i)

# Wrapper owns the close
async def all_producers(ch: Channel[int]) -> None:
    try:
        await asyncio.gather(producer_a(ch), producer_b(ch))
    finally:
        ch.close()
```

If you let each producer close the channel independently, the first one to finish will close it
while others are still running, causing their `put` calls to raise `ChannelClosed`.

---

## Pattern 3 — Pipeline: each stage closes its output channel in `finally`

In a multi-stage pipeline every intermediate stage reads from one channel and writes to the next.
The rule is the same: whoever writes to a channel is responsible for closing it.

```python
async def fetch_stage(out: Channel[str]) -> None:
    try:
        for url in urls:
            await out.put(await fetch(url))
    finally:
        out.close()

async def parse_stage(inp: Channel[str], out: Channel[dict]) -> None:
    try:
        async for raw in inp:
            await out.put(parse(raw))
    finally:
        out.close()  # closes the next stage's input when inp is exhausted

async def store_stage(inp: Channel[dict]) -> None:
    async for record in inp:
        await db.insert(record)
```

```python
raw_ch: Channel[str] = Channel(20)
parsed_ch: Channel[dict] = Channel(20)

await asyncio.gather(
    fetch_stage(raw_ch),
    parse_stage(raw_ch, parsed_ch),
    store_stage(parsed_ch),
)
```

The close propagates automatically: `fetch_stage` closes `raw_ch` → `parse_stage`'s `async for`
exits → `parse_stage` closes `parsed_ch` → `store_stage`'s `async for` exits.

---

## Pattern 4 — Batch consumer (get_nowait drain loop)

For batching work (e.g. bulk DB inserts), drain as many items as available without blocking, then
sleep briefly when the channel is live but temporarily empty:

```python
async def batch_consumer(ch: Channel[Row]) -> None:
    while not ch.closed() or not ch.empty():
        batch: list[Row] = []
        while len(batch) < 100:
            try:
                batch.append(ch.get_nowait())
            except (ChannelEmpty, ChannelClosed):
                break
        if batch:
            await db.bulk_insert(batch)
        else:
            await asyncio.sleep(1)  # yield while producer catches up
```

The outer `while not ch.closed() or not ch.empty()` is the correct drain condition:
- `not ch.closed()` — keep looping while the producer can still send more
- `not ch.empty()` — keep looping while items remain even after close

Both conditions together ensure you process every item before exiting.

---

## Pattern 5 — Buffered channels for back-pressure

Pass `maxsize` to limit how far ahead a fast producer can run. When the buffer is full, `put`
blocks until a consumer has freed a slot:

```python
# producer can be at most 20 items ahead of the consumer
ch: Channel[bytes] = Channel(20)
```

Use a buffer when the producer is faster than the consumer and you want to smooth out bursts
without letting memory grow without bound.

---

## Error propagation

Exceptions in tasks surface when you **await the task**, not via the channel. The channel just
signals completion — it carries no error information. Structure your orchestrator to await tasks
in dependency order:

```python
producer_task = asyncio.create_task(producer(ch))
consumer_task = asyncio.create_task(consumer(ch))

await producer_task   # if the producer raised, the exception re-raises here
await consumer_task   # consumer exits cleanly because producer closed ch in finally
```

Because the producer closes the channel in `finally` (even when it raises), the consumer will
always drain and exit — you won't have a zombie consumer task waiting forever. The exception
propagates to the caller via `await producer_task`, giving you clean error handling without any
special channel-level error protocol.

If you're using `asyncio.gather` at the top level and want errors to cancel siblings immediately,
pass `return_exceptions=False` (the default) — a task exception will cancel the gather and
propagate. If siblings need to finish regardless, use `return_exceptions=True` and inspect the
results list.

---

## Quick checklist

- [ ] Every producer closes its output channel in a `finally` block
- [ ] Multiple producers? Use a wrapper that gathers them and closes in `finally`; individuals don't close
- [ ] Pipeline stages close their *output* channel in `finally` after consuming their *input*
- [ ] Batch consumers use `while not ch.closed() or not ch.empty()` — both conditions together
- [ ] Errors surface via `await task`, not via the channel; rely on `finally`-close to unblock consumers
