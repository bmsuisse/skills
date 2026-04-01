# FastAPI Server-Sent Events (SSE)

> Source: https://fastapi.tiangolo.com/tutorial/server-sent-events/
> Added in FastAPI 0.135.0

SSE streams `text/event-stream` data to browsers via the native `EventSource` API. Common uses: AI chat streaming, live notifications, logs.

## Basic SSE endpoint

```python
from collections.abc import AsyncIterable
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

items = [
    Item(name="Plumbus", price=32.99),
    Item(name="Portal Gun", price=999.99),
]

@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items() -> AsyncIterable[Item]:
    for item in items:
        yield item  # auto-encoded as JSON in the `data:` field
```

Use `response_class=EventSourceResponse` and `yield` items. Declare `AsyncIterable[Item]` return type for Pydantic validation + higher performance (Rust-side serialization).

## ServerSentEvent — set event, id, retry, comment

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(comment="stream of item updates")
    for i, item in enumerate(items):
        yield ServerSentEvent(data=item, event="item_update", id=str(i + 1), retry=5000)
```

## Raw data (no JSON encoding)

```python
@app.get("/logs/stream", response_class=EventSourceResponse)
async def stream_logs() -> AsyncIterable[ServerSentEvent]:
    for log_line in ["INFO started", "DEBUG connected", "WARN high memory"]:
        yield ServerSentEvent(raw_data=log_line)
```

`raw_data` and `data` are mutually exclusive per event.

## Resuming with Last-Event-ID

```python
from typing import Annotated
from fastapi import Header

@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items(
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    start = last_event_id + 1 if last_event_id is not None else 0
    for i, item in enumerate(items):
        if i < start:
            continue
        yield ServerSentEvent(data=item, id=str(i))
```

## SSE with POST (e.g. AI chat, MCP)

```python
class Prompt(BaseModel):
    text: str

@app.post("/chat/stream", response_class=EventSourceResponse)
async def stream_chat(prompt: Prompt) -> AsyncIterable[ServerSentEvent]:
    for word in prompt.text.split():
        yield ServerSentEvent(data=word, event="token")
    yield ServerSentEvent(raw_data="[DONE]", event="done")
```

## Non-async (sync) generator

```python
from collections.abc import Iterable

@app.get("/items/stream-sync", response_class=EventSourceResponse)
def stream_sync() -> Iterable[Item]:
    for item in items:
        yield item
```

FastAPI runs sync generators off the event loop automatically.

## What FastAPI handles automatically

- Keep-alive ping comment every 15 s (prevents proxy timeouts)
- `Cache-Control: no-cache` header
- `X-Accel-Buffering: no` header (prevents Nginx buffering)
