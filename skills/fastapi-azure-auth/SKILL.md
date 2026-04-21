---
name: fastapi-azure-auth
plugin: coding
description: >
  Azure Entra ID SSO for FastAPI using cookie-based sessions (MSAL, /login →
  /callback → session). Trigger on: Azure AD login, Entra SSO, protect routes,
  RBAC, DEV_MODE bypass, download links with auth. Covers App Registration,
  AuthMiddleware, role checks via Postgres, and cookie auth enabling native
  <a download> links.
---

# FastAPI Azure Entra ID Auth

OAuth2 authorization code flow using MSAL, Starlette sessions, and raw asyncpg RBAC.
Designed for the init-app-stack: FastAPI + Granian + asyncpg + uv + Python 3.14.

## Why cookie-based auth

This approach stores the session in an encrypted cookie rather than a Bearer token.
The key advantage: **`<a href="/api/files/report.pdf" download>` links work out of the box.**
Browsers automatically send cookies on direct navigation — they cannot inject an
`Authorization` header for `<a>` tag clicks. If you used token-based auth, file
download links would require a JavaScript fetch + blob URL workaround instead.

## Packages

```bash
uv add msal starlette pem
# starlette is already a fastapi dependency — just needs session middleware enabled
```

## File structure

```
app/
├── auth/
│   ├── setup.py        ← registers /login, /callback, /logout + AuthMiddleware
│   └── credentials.py  ← returns client secret or certificate dict for MSAL
└── utils/
    └── auth.py         ← get_user_email(), get_user_role(), require_* helpers
main.py                 ← calls auth.setup(app) unless DEV_MODE
```

## `app/auth/credentials.py`

Returns the credential MSAL expects — either a plain string (client secret) or
a dict with `private_key`, `thumbprint`, and `certificate` (certificate auth).
Certificate auth is preferred for production; secret is fine for development.

```python
from __future__ import annotations
import os
from pathlib import Path
import pem


def get_credential() -> str | dict:
    if secret := os.getenv("APP_REG_CLIENT_SECRET"):
        return secret

    cert_str = os.getenv("APP_REG_CLIENT_CERT") or Path("app/auth/_certs/cert.pem").read_text()
    thumbprint = os.getenv("APP_REG_CLIENT_THUMBPRINT", "")
    parts = pem.parse(cert_str)
    return {
        "private_key":  str(next(p for p in parts if isinstance(p, pem.PrivateKey))),
        "certificate":  str(next(p for p in parts if isinstance(p, pem.Certificate))),
        "thumbprint":   thumbprint,
    }
```

## `app/auth/setup.py`

Call `setup(app)` once at startup. It wires three endpoints and one middleware.

```python
from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from msal import ConfidentialClientApplication
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger(__name__)

# Paths that bypass auth entirely
PUBLIC_PATHS = ["/login", "/callback", "/logout", "/docs", "/redoc", "/openapi.json"]


def setup(app: FastAPI, *, tenant_id: str) -> dict:
    """
    Wire Azure Entra SSO onto an existing FastAPI app.

    Returns {"msal_app": ..., "user_dependency": ...} so callers can check
    whether auth is active (msal_app is None when APP_REG_CLIENT_ID is unset).
    """
    msal_app = None
    client_id = os.getenv("APP_REG_CLIENT_ID")

    if client_id:
        try:
            app.add_middleware(
                SessionMiddleware,
                secret_key=os.getenv("API_COOKIE_SECRET", "change-me-in-production"),
                max_age=60 * 60 * 24,  # 24 h
            )
            from app.auth.credentials import get_credential

            msal_app = ConfidentialClientApplication(
                client_id,
                authority=f"https://login.microsoftonline.com/{tenant_id}",
                client_credential=get_credential(),
            )
        except Exception:
            logger.exception("Failed to initialise MSAL")

    # ── Middleware ────────────────────────────────────────────────────────────

    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            if any(path.startswith(p) for p in PUBLIC_PATHS):
                return await call_next(request)

            user = request.session.get("user") if hasattr(request, "session") else None

            if path.startswith("/api/"):
                if not user:
                    return Response(status_code=status.HTTP_401_UNAUTHORIZED)
            else:
                if not user:
                    return RedirectResponse(f"/login?redirect_uri={path}")

            return await call_next(request)

    app.add_middleware(AuthMiddleware)

    # ── /login ────────────────────────────────────────────────────────────────

    @app.get("/login")
    async def login(request: Request, redirect_uri: Optional[str] = None):
        if msal_app is None:
            return {"message": "Auth not configured — set APP_REG_CLIENT_ID"}

        base = str(request.base_url).rstrip("/")
        callback = base + "/callback"
        # Force HTTPS when not on localhost
        if request.url.hostname not in ("localhost", "127.0.0.1", "::1"):
            callback = os.getenv("APP_REG_REDIRECT_URI", callback).replace("http://", "https://")

        flow = msal_app.initiate_auth_code_flow(["email"], redirect_uri=callback)
        flow["redir_url"] = redirect_uri or "/"

        resp = RedirectResponse(flow["auth_uri"])
        resp.set_cookie("flow", json.dumps(flow, default=str), max_age=180, httponly=True)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ── /callback ────────────────────────────────────────────────────────────

    @app.get("/callback")
    async def callback(request: Request):
        if msal_app is None:
            return {"message": "Auth not configured"}

        flow = json.loads(request.cookies.get("flow", "{}"))
        redir = flow.get("redir_url", "/")
        if "://" in redir:          # prevent open redirect
            redir = "/"

        ts = int(datetime.now(tz=timezone.utc).timestamp())
        redir += ("&" if "?" in redir else "?") + f"_={ts}"

        result = msal_app.acquire_token_by_auth_code_flow(
            auth_code_flow=flow,
            auth_response=dict(request.query_params),
        )

        resp = RedirectResponse(redir)
        resp.delete_cookie("flow")

        if "error" in result:
            # Code already redeemed (54005) — clear everything and restart
            if 54005 in result.get("error_codes", []):
                for k in request.cookies:
                    resp.delete_cookie(k)
                return resp
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=result["error"])

        request.session["user"] = result["id_token_claims"]
        return resp

    # ── /logout ───────────────────────────────────────────────────────────────

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/")

    # ── dependency ────────────────────────────────────────────────────────────

    async def current_user(request: Request) -> dict:
        user = request.session.get("user")
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)
        return user

    return {"msal_app": msal_app, "user_dependency": current_user}
```

## `app/utils/auth.py`

Role helpers that work with asyncpg (t-string SQL) and a 5-minute in-process cache.

```python
from __future__ import annotations
import os
import time
from typing import Final

from fastapi import HTTPException, Request

from db import pool, sql          # init-app-stack db helpers

_DEV_MODE  = os.getenv("DEV_MODE",  "false").lower() in ("1", "true", "t")
_TEST_MODE = os.getenv("TEST_MODE", "false").lower() in ("1", "true", "t")

ROLE_CACHE_TTL: Final[int] = 300   # seconds
_role_cache: dict[str, tuple[str | None, float]] = {}


def get_user_email(request: Request) -> str:
    if _TEST_MODE:
        return request.headers.get("X-Test-User", "test.user@example.com").lower()
    if _DEV_MODE:
        return "dev.user@example.com"
    email = request.session.get("user", {}).get("email")
    if not email:
        raise HTTPException(401, "Unauthorized")
    return email.lower()


async def get_user_role(request: Request) -> str | None:
    email = get_user_email(request)
    cached = _role_cache.get(email)
    now = time.monotonic()
    if cached and cached[1] > now:
        return cached[0]

    async with pool.acquire() as conn:
        row = await conn.fetchrow(*sql(
            t"SELECT role FROM dim.user_roles WHERE email = {email}"
        ))

    role = row["role"] if row else None
    _role_cache[email] = (role, now + ROLE_CACHE_TTL)
    return role


async def require_role(request: Request) -> str:
    role = await get_user_role(request)
    if not role:
        raise HTTPException(403, "Forbidden")
    return role


async def require_write(request: Request) -> str:
    """Block read-only roles."""
    role = await require_role(request)
    if role in {"reader"}:
        raise HTTPException(403, "Forbidden")
    return role
```

## `main.py` — wiring it in

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import init_pool, close_pool

TENANT_ID = os.environ["AZURE_TENANT_ID"]   # put in .env, not hardcoded
DEV_MODE  = os.getenv("DEV_MODE", "false").lower() in ("1", "true", "t")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()

app = FastAPI(lifespan=lifespan)

if not DEV_MODE:
    from app.auth.setup import setup
    setup(app, tenant_id=TENANT_ID)
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `AZURE_TENANT_ID` | Yes | Entra ID tenant ID (directory ID in Azure portal) |
| `APP_REG_CLIENT_ID` | Yes (prod) | App registration client ID — omit to disable auth |
| `APP_REG_CLIENT_SECRET` | One of these | Client secret from app registration |
| `APP_REG_CLIENT_CERT` | One of these | PEM string with private key + certificate |
| `APP_REG_CLIENT_THUMBPRINT` | With cert | Certificate thumbprint |
| `APP_REG_REDIRECT_URI` | Prod | Full callback URL, e.g. `https://myapp.azurecontainerapps.io/callback` |
| `API_COOKIE_SECRET` | Yes (prod) | Random secret for session cookie — `openssl rand -hex 32` |
| `DEV_MODE` | Dev | Set `true` to skip auth entirely and use a fake user |

## User roles table

```sql
CREATE TABLE dim.user_roles (
    email TEXT PRIMARY KEY,
    role  TEXT NOT NULL   -- e.g. admin, editor, reader
);
```

## Azure App Registration checklist

1. **New registration** — single tenant, any name
2. **Redirect URI** — Web → `https://yourdomain/callback` (and `http://localhost:8000/callback` for dev)
3. **ID tokens** — Authentication → enable *ID tokens* under Implicit grant
4. **Client secret** — Certificates & secrets → New client secret (or upload a certificate)
5. **Copy** — Application (client) ID + Directory (tenant) ID → `.env`

## DEV_MODE local workflow

```bash
# .env
DEV_MODE=true
```

With `DEV_MODE=true`, auth setup is skipped entirely and `get_user_email()` returns
`dev.user@example.com`. Insert a row for that email in `dim.user_roles` to test RBAC
without touching Microsoft login.

## Protected endpoint example

```python
from fastapi import Depends
from app.utils.auth import get_user_email, require_write

@app.get("/api/items")
async def list_items(request: Request, _=Depends(require_role)):
    email = get_user_email(request)
    ...

@app.post("/api/items")
async def create_item(request: Request, _=Depends(require_write)):
    ...
```
