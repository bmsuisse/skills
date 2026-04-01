# FastAPI Server-Sent Events (SSE)

> Source: https://fastapi.tiangolo.com/tutorial/server-sent-events/
> Added in FastAPI 0.135.0 — not covered by most AI training data.
> Use `from fastapi.sse import EventSourceResponse, ServerSentEvent` — NOT `sse-starlette`.

SSE streams `text/event-stream` data to browsers via the native `EventSource` API.
Common uses: AI chat token streaming, live notifications, log tailing, observability feeds.

## How it works

The client connects once (HTTP GET or POST), and the server keeps the connection open, pushing
newline-delimited text blocks. Browsers reconnect automatically if the connection drops.

```
data: {"name": "Portal Gun", "price": 999.99}

data: {"name": "Plumbus", "price": 32.99}

```

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

Use `response_class=EventSourceResponse` and `yield` items from an `async def` generator.
Declare `AsyncIterable[Item]` return type for Pydantic validation + Rust-side serialization performance.

## ServerSentEvent — set event, id, retry, comment

For fine-grained control over the SSE protocol fields:

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(comment="stream of item updates")  # keep-alive / metadata
    for i, item in enumerate(items):
        yield ServerSentEvent(
            data=item,           # Pydantic model or dict, auto JSON-encoded
            event="item_update", # event type (client listens with addEventListener)
            id=str(i + 1),       # event ID for Last-Event-ID resumption
            retry=5000,          # ms before client retries on disconnect
        )
```

## Raw data (no JSON encoding)

Use `raw_data` for pre-formatted strings, log lines, or special sentinel values like `[DONE]`:

```python
@app.get("/logs/stream", response_class=EventSourceResponse)
async def stream_logs() -> AsyncIterable[ServerSentEvent]:
    logs = [
        "2025-01-01 INFO  Application started",
        "2025-01-01 DEBUG Connected to database",
        "2025-01-01 WARN  High memory usage detected",
    ]
    for log_line in logs:
        yield ServerSentEvent(raw_data=log_line)
```

`raw_data` and `data` are mutually exclusive per event.

## Resuming with Last-Event-ID

Browsers automatically send `Last-Event-ID` on reconnect. Use it to resume from where you left off:

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

## SSE with POST (AI chat, MCP, form submissions)

SSE works with any HTTP method — POST is common for AI chat where you send a prompt body:

```python
class Prompt(BaseModel):
    text: str

@app.post("/chat/stream", response_class=EventSourceResponse)
async def stream_chat(prompt: Prompt) -> AsyncIterable[ServerSentEvent]:
    async for token in llm_stream(prompt.text):          # async generator from your LLM client
        yield ServerSentEvent(data=token, event="token")
    yield ServerSentEvent(raw_data="[DONE]", event="done")
```

Note: browsers' native `EventSource` API only supports GET. For POST-based SSE, use `fetch()` with
a `ReadableStream` on the client side, or a library like `@microsoft/fetch-event-source`.

## Real-time database / queue streaming

```python
import asyncio

@app.get("/queue/stream", response_class=EventSourceResponse)
async def stream_queue(db: AsyncSession = Depends(get_db)) -> AsyncIterable[ServerSentEvent]:
    while True:
        messages = await message_repository.get_pending(db)
        for msg in messages:
            yield ServerSentEvent(data=msg, event="message", id=str(msg.id))
            await message_repository.mark_sent(db, msg.id)
        await asyncio.sleep(1)  # poll interval
```

## What FastAPI handles automatically

- Keep-alive ping comment every 15 s when idle (prevents proxy connection closure)
- `Cache-Control: no-cache` header
- `X-Accel-Buffering: no` header (prevents Nginx/proxy buffering)

No additional configuration needed.

## Client-side (browser EventSource)

```javascript
// GET endpoint
const source = new EventSource("/items/stream");
source.addEventListener("item_update", (e) => {
    const item = JSON.parse(e.data);
    console.log(item);
});
source.onerror = () => source.close();

// POST endpoint — use fetch + ReadableStream
const response = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: "hello" }),
});
const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    console.log(decoder.decode(value));
}
```
