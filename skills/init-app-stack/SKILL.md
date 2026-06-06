---
name: init-app-stack
plugin: coding
description: Use this skill whenever the user wants to bootstrap, scaffold, or initialize a new full-stack app with a Vite + React + TanStack + shadcn/ui frontend and a FastAPI + Postgres backend. Triggers on requests like "create a new app", "set up a project", "scaffold a full-stack app", "init a new project", or anything involving starting a fresh React/FastAPI application from scratch.
---

# Init App Stack

Bootstrap a full-stack project with:

- **Frontend**: Vite **8+** + React + TanStack Router + TanStack Query + TanStack Form + TanStack Table + TanStack Virtual + Zustand + **shadcn/ui** + TailwindCSS v4, managed with **bun**
- **Backend**: FastAPI + Granian + raw **asyncpg** (Postgres), managed with **uv**, targeting **Python 3.14** (PEP 750 t-strings for SQL)
- **DB**: Postgres 17 via `docker-compose.yml`
- **Types**: `openapi-typescript` generates a typed client from FastAPI's OpenAPI schema
- **Ports**: randomly assigned high ports (seeded by project name, so deterministic per project — printed on scaffold completion)

## Step 1: Run the scaffold script

This creates the full project structure deterministically — do not scaffold manually.

```bash
uv run python scripts/create.py <project-name>
```

The script (works on Mac, Linux, Windows):

1. **Frontend**: `bun create vite@latest frontend --template react-ts`, installs TanStack Router + Query + Form + Table + Virtual + unified Devtools, Zustand, Zod, TailwindCSS v4, shadcn deps (`class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `tw-animate-css`), `openapi-typescript`
2. Wires `vite.config.ts` with `@tanstack/router-plugin` + `@/` path alias, sets up `src/main.tsx` with `QueryClientProvider` + `RouterProvider`, writes `src/routes/__root.tsx` and `src/routes/index.tsx`
3. Writes `src/lib/queryClient.ts`, `src/lib/api.ts` (fetch wrapper with `VITE_API_URL`), `src/lib/utils.ts` (shadcn `cn` helper), `src/stores/` placeholder for Zustand
4. Writes shadcn config: `components.json`, shadcn-compatible `src/index.css` (OKLCH theme vars, `@theme inline`, `tw-animate-css`, `.dark` class variant), patches `tsconfig.json` + `tsconfig.app.json` with `@/*` path alias
5. Adds `bun run generate-api` script → fetches `/openapi.json` and runs `openapi-typescript` into `src/lib/api-types.ts`
6. **Backend**: `uv init --python 3.14` at **project root**, adds `fastapi`, `granian`, `asyncpg`, `pydantic-settings`
7. Writes `backend/main.py` (lifespan-managed asyncpg pool, CORS for `localhost:5173`), `backend/db.py` (pool + t-string `sql()` helper), `backend/config.py` (pydantic-settings) — all imports use `from backend.xxx import ...`
8. Adds `dev = "backend.scripts:dev"` and `start = "backend.scripts:start"` to root `pyproject.toml`; granian target is `backend.main:app`
9. Writes `docker-compose.yml` with a single `db` service (Postgres 17) + named volume
10. Writes `.env.example` (frontend + backend), root `.gitignore`, `README.md` with startup steps

After running:

```bash
cd <project-name>
docker compose up -d db           # start Postgres
uv run dev                        # FastAPI on :8000 (run from project root)
cd frontend && bun run dev        # Vite on :5173
```

## Step 2: Set up code formatting with prek

After scaffolding, run `/prek` to configure formatters for the whole project.
This writes `prek.toml`, updates root `pyproject.toml`, adds `.prettierrc`, installs
the git pre-commit hook, and formats all existing files. The project has both
Python (`backend/`) and TypeScript (`frontend/`) so prek will configure both
ruff and prettier automatically.

## Step 3: Enable companion skills via marketplace

Add this to your project's `.claude/settings.json` to give the agent deep knowledge of the stack:

```json
{
  "extraKnownMarketplaces": {
    "bmsuisse-skills": {
      "source": {
        "source": "github",
        "repo": "bmsuisse/skills"
      }
    }
  },
  "enabledPlugins": {
    "coding@bmsuisse-skills": true
  }
}
```

This installs the `coding` plugin which includes:

- `tanstack-best-practices` — TanStack Router + Query patterns, SSR integration, query key factories
- `coding-guidelines-typescript` — TypeScript strictness, discriminated unions, async typing
- `coding-guidelines-python` — FastAPI/backend Python standards, ty type checking
- `fastapi-guideline` — Production FastAPI patterns (CRUD, DI, auth, async)
- `autoresearch` — Autonomous experiment loop for iterative improvements

---

## Reference files (load as needed, not all at once)

| File                                                                     | When to read                                                                 |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| [`references/react-tanstack.md`](references/react-tanstack.md)           | TanStack Router (typed routes, search params, loaders) + Query (caching, mutations) + Zustand patterns |
| [`references/shadcn-ui.md`](references/shadcn-ui.md)                     | Adding shadcn components, theme tokens, `cn()` usage, dark mode              |
| [`references/asyncpg-postgres.md`](references/asyncpg-postgres.md)       | Connection pool lifecycle, t-string `sql()` helper, transactions, pagination |
| [`references/openapi-typed-client.md`](references/openapi-typed-client.md) | Regenerating `api-types.ts` from FastAPI, typed fetch patterns              |
| [`references/fastapi-templates.md`](references/fastapi-templates.md)     | Backend structure, CRUD repos, dependency injection, auth                    |
| [`references/fastapi-sse.md`](references/fastapi-sse.md)                 | Adding SSE streaming endpoints (AI chat, live updates, logs)                 |
| [`references/frontend-design.md`](references/frontend-design.md)         | UI aesthetics, typography, color, motion — avoid generic looks               |

---

## Key conventions

- Always use **bun** (not npm/yarn/pnpm) for the frontend.
- Always use **uv** (not pip/poetry/pipenv) for the backend. Pin Python **3.14**.
- Backend uses `fastapi` + `granian` — do **not** use `fastapi[standard]` (bundles uvicorn, conflicts with Granian).
- Run backend dev with `uv run dev` (`granian --interface asgi main:app --reload`).
- **Do not use SQLAlchemy or any ORM.** Use raw asyncpg with the `sql()` t-string helper in `backend/db.py`:
  ```python
  from backend.db import sql, pool
  async with pool.acquire() as conn:
      rows = await conn.fetch(*sql(t"SELECT * FROM users WHERE id = {user_id}"))
  ```
  The helper converts `t"..."` interpolations to asyncpg's native `$1, $2` positional params — safe from injection, no string formatting.
- Frontend routing: **file-based** via `@tanstack/router-plugin` — add files under `src/routes/`, route tree is auto-generated.
- Data fetching: **TanStack Query** only — do not roll `useEffect + fetch`. Use `queryOptions` for reusable query definitions.
- Forms: **TanStack Form** (`@tanstack/react-form`) — use `useForm` + `form.Field` with shadcn input/label primitives. Do not add react-hook-form.
- Tables: **TanStack Table** (`@tanstack/react-table`) — headless; you own the markup. Use `useReactTable` + `getCoreRowModel()`.
- Long lists: **TanStack Virtual** (`@tanstack/react-virtual`) — use `useVirtualizer` when rendering 100+ rows.
- Client state: start with `useState` + Context. Reach for **Zustand** only when syncing across distant components. Never Redux.
- URL state (filters, pagination, sort): put in TanStack Router search params with Zod validation, not in Zustand.
- UI components: **shadcn/ui** — generated into `src/components/ui/` via `bunx --bun shadcn@latest add <component>`. Do not install a MUI/Chakra/Mantine. Style with Tailwind v4 tokens (`bg-background`, `text-foreground`, `text-muted-foreground`, `border-border`) — not raw palette colors like `bg-neutral-800`.
- Use the `cn()` helper from `@/lib/utils` to conditionally merge Tailwind classes. Imports use the `@/*` alias (configured in `vite.config.ts` + both tsconfigs).
- Regenerate API types after backend changes: `bun run generate-api` (requires backend running on `localhost:8000`).
- CORS is pre-configured for the project's assigned frontend port (seeded from project name). Update for production.
- Typing on backend: `uv add --dev ty` and run `uv run ty check`.
