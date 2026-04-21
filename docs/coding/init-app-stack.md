---
title: Init App Stack
description: Scaffold a full-stack Vite + React + TanStack + shadcn/ui + FastAPI + Postgres app in one command.
---

# Init App Stack

**Skill:** `init-app-stack` · **Plugin:** `coding@bmsuisse-skills`

Bootstrap a production-ready full-stack project in one command.

## Stack

| Layer | Technology |
|---|---|
| Frontend runtime | Vite 8+ + React + TypeScript |
| Routing | TanStack Router (file-based) |
| Data fetching | TanStack Query |
| Client state | Zustand (use sparingly) |
| UI components | shadcn/ui + TailwindCSS v4 |
| Frontend package manager | **bun** |
| Backend | FastAPI + Granian + asyncpg |
| Backend package manager | **uv** (Python 3.14) |
| Database | Postgres 17 (Docker) |
| API types | openapi-typescript (auto-generated) |

## Quick start

```bash
# 1. Scaffold
uv run python scripts/create.py my-app

# 2. Enable companion skills (add to .claude/settings.json)
{
  "extraKnownMarketplaces": {
    "bmsuisse-skills": { "source": { "source": "github", "repo": "bmsuisse/skills" } }
  },
  "enabledPlugins": { "coding@bmsuisse-skills": true }
}

# 3. Start services
cd my-app
docker compose up -d db
cd backend  && uv run dev    # FastAPI on :8000
cd frontend && bun run dev   # Vite on :5173
```

## Key conventions

**Always use bun for frontend:**
```bash
bun add @tanstack/react-query
bunx --bun shadcn@latest add button
```

**Always use uv for backend:**
```bash
uv add fastapi
uv run dev        # runs granian --interface asgi main:app --reload
```

**SQL with t-strings (no ORM):**
```python
from db import sql, pool

async with pool.acquire() as conn:
    rows = await conn.fetch(*sql(t"SELECT * FROM users WHERE id = {user_id}"))
```
The `sql()` helper converts t-string interpolations to asyncpg's `$1, $2` positional params — injection-safe, no string formatting.

**TanStack Router — file-based routing:**

Add files under `src/routes/` and the route tree is auto-generated:

```
src/routes/
├── __root.tsx          # root layout
├── index.tsx           # /
├── users/
│   ├── index.tsx       # /users
│   └── $id.tsx         # /users/:id
```

**URL state in search params, not Zustand:**
```typescript
// ✅ filters, pagination, sort → TanStack Router search params
const { page, sort } = Route.useSearch();

// ❌ don't put URL-sharable state in Zustand
const { page } = useFilterStore();
```

**shadcn/ui tokens only:**
```tsx
// ✅
<div className="bg-background text-foreground border-border" />

// ❌ don't use raw palette
<div className="bg-neutral-800 text-white" />
```

## Regenerate API types

After changing the FastAPI backend:

```bash
bun run generate-api   # requires backend on localhost:8000
```

This updates `src/lib/api-types.ts` from `/openapi.json`.
