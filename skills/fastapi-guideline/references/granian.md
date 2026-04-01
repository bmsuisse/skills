# Granian — Rust HTTP Server for Python

> https://github.com/emmett-framework/granian
> Replaces uvicorn + gunicorn with a single Rust-native ASGI server.

Granian is the preferred server for FastAPI in this project. It supports HTTP/1, HTTP/2, WebSockets,
and ASGI natively. No need for a uvicorn/gunicorn stack.

## Installation

```bash
uv add granian           # basic
uv add granian[reload]   # + auto-reload for dev
uv add granian[uvloop]   # + uvloop event loop (Linux/macOS, higher throughput)
uv add granian[winloop]  # + winloop event loop (Windows)
```

## Running a FastAPI app

```bash
# development
uv run granian --interface asgi main:app --reload

# production (single process)
uv run granian --interface asgi main:app --host 0.0.0.0 --port 8000

# production (multi-process — match to CPU cores)
uv run granian --interface asgi main:app --host 0.0.0.0 --port 8000 --workers 4
```

`main:app` — Python module `main`, attribute `app` (your FastAPI instance).

## Essential CLI options

| Option | Default | Purpose |
|--------|---------|---------|
| `--interface asgi` | required | Use ASGI mode (FastAPI is ASGI) |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8000` | Port |
| `--workers` | `1` | Worker processes |
| `--http [auto\|1\|2]` | `auto` | HTTP version (auto negotiates HTTP/2) |
| `--loop [auto\|asyncio\|uvloop\|rloop\|winloop]` | `auto` | Event loop backend |
| `--reload` | off | Auto-reload on code changes (requires `granian[reload]`) |
| `--backpressure` | — | Max concurrent requests per worker |
| `--log-level [debug\|info\|warn\|error]` | `info` | Log verbosity |

## pyproject.toml integration

```toml
[tool.uv.scripts]
dev   = "granian --interface asgi main:app --reload --log-level debug"
start = "granian --interface asgi main:app --host 0.0.0.0 --port 8000 --workers 4"
```

```bash
uv run dev    # development
uv run start  # production
```

## Worker model

- **Workers**: separate OS processes, each with its own Python interpreter and event loop.
- **Blocking threads**: threads per worker that interact with Python (default: 1).
- **Runtime threads**: Rust threads handling network I/O per worker (default: 1).

For most deployments: 1 worker per container (Kubernetes), or match workers to CPU cores for bare metal.

## HTTP/2

Granian supports HTTP/2 out of the box. For TLS-terminated HTTP/2 behind a proxy (nginx, caddy):

```bash
uv run granian --interface asgi main:app --http 2
```

For direct TLS (mTLS included):

```bash
uv run granian --interface asgi main:app \
  --http 2 \
  --ssl-certificate cert.pem \
  --ssl-keyfile key.pem
```

## Event loop selection

```bash
# Linux/macOS — uvloop is fastest
uv add granian[uvloop]
uv run granian --interface asgi main:app --loop uvloop

# Windows
uv add granian[winloop]
uv run granian --interface asgi main:app --loop winloop
```

## Comparison to uvicorn

| | Granian | uvicorn |
|--|---------|---------|
| Language | Rust core | Pure Python |
| HTTP/2 | Native | Requires h2 extra |
| Multi-process | Built-in `--workers` | Needs gunicorn |
| WebSockets | Native | Native |
| Reload | `granian[reload]` | `--reload` flag |
| Install | `uv add granian` | `uv add uvicorn` |

Do not install or use uvicorn — Granian replaces it entirely.
