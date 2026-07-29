---
name: init-app-stack
plugin: coding
description: Use this skill whenever the user wants to bootstrap, scaffold, or initialize a new full-stack app with a Vite + React + TanStack + shadcn/ui frontend and a FastAPI + Postgres backend. Triggers on requests like "create a new app", "set up a project", "scaffold a full-stack app", "init a new project", or anything involving starting a fresh React/FastAPI application from scratch.
---

# Init App Stack

Bootstrap a full-stack project with:

- **Frontend**: Vite **8+** + React + TanStack Router + TanStack Query + TanStack Form + TanStack Table + TanStack Virtual + Zustand + **shadcn/ui** + TailwindCSS v4, managed with **bun**
- **Backend**: FastAPI + Granian + **[pgdevkit](https://github.com/bmsuisse/pgdevkit)** (psycopg, no ORM), managed with **uv**, targeting **Python 3.14**
- **DB**: Postgres 17 via `docker-compose.yml` for dev; pgdevkit's `pgdb testdb` for tests; schema lives as `.sql` files under `database/`
- **Types**: [`@hey-api/openapi-ts`](https://openapi-ts.dev) generates a typed SDK, TanStack Query options, and Zod runtime validators from FastAPI's OpenAPI schema — the generated output is committed, not gitignored
- **Task runner**: [`just`](https://github.com/casey/just) — the scaffold writes a root `justfile` (`install`, `db-up`, `db-down`, `backend`, `frontend`, `dev`, `generate-api`). `just dev` runs backend + frontend together (Ctrl+C stops both); it does not start Postgres — run `just db-up` first. It uses `set shell := ["bash", "-uc"]` for `&`/`wait`, so Git Bash must be on `PATH` on Windows. Run `just` with no args to list recipes; always drive the project through `just <recipe>` instead of raw `uv run` / `bun run` / `docker compose` commands.
- **Ports**: randomly assigned high ports (seeded by project name, so deterministic per project — printed on scaffold completion)

## Step 1: Run the scaffold script

This creates the full project structure deterministically — do not scaffold manually.

```bash
uv run python scripts/create.py <project-name>
```

The script (works on Mac, Linux, Windows):

1. **Frontend**: `bun create vite@latest frontend --template react-ts`, installs TanStack Router + Query + Form + Table + Virtual + unified Devtools, Zustand, Zod, TailwindCSS v4, shadcn deps (`class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `tw-animate-css`), `@heroicons/react` (app-level icons — see [`bms-frontend-design`](../bms-frontend-design/)), `@hey-api/openapi-ts` (dev dep — the `@hey-api/client-fetch` runtime it configures is bundled into the generated output, not installed separately)
2. Wires `vite.config.ts` with `@tanstack/router-plugin` + `@/` path alias, sets up `src/main.tsx` with `QueryClientProvider` + `RouterProvider` (and a side-effect `import './lib/api'` to configure the generated client before any query runs), writes `src/routes/__root.tsx` and `src/routes/index.tsx`
3. Writes `src/lib/queryClient.ts`, `src/lib/api.ts` (configures the generated client's `baseUrl`/`credentials` from `VITE_API_URL`), `src/lib/utils.ts` (shadcn `cn` helper), `src/stores/` placeholder for Zustand, `frontend/openapi-ts.config.ts` (`@hey-api/openapi-ts` config: `@tanstack/react-query` + `zod` + `@hey-api/sdk` plugins, zod request validation, output → `src/lib/generated/`)
4. Writes shadcn config: `components.json`, shadcn-compatible `src/index.css` (OKLCH theme vars, `@theme inline`, `tw-animate-css`, `.dark` class variant), patches `tsconfig.json` + `tsconfig.app.json` with `@/*` path alias
5. Adds `bun run generate-api` script → runs `openapi-ts` against the local `frontend/openapi.json` (see step 7's `dump_openapi.py`)
6. **Backend**: `uv init --python 3.14` at **project root**, adds `fastapi`, `granian`, `pydantic-settings`, `pgdevkit[cli,db]`, plus `pytest`/`pytest-asyncio` as dev deps
7. Writes `backend/main.py` (lifespan-managed `pgdevkit.db.PgPool`, CORS for `localhost:5173`, `/health` with `operation_id="health"` for a clean generated name), `backend/db.py` (`PgPool(env_prefix="APP_POSTGRES_")`), `backend/config.py` (pydantic-settings, CORS only), `backend/dump_openapi.py` (imports `backend.main.app` directly and writes `app.openapi()` to `frontend/openapi.json` — no running server or DB needed) — all imports use `from backend.xxx import ...`
8. Adds `dev = "backend.scripts:dev"` and `start = "backend.scripts:start"` to root `pyproject.toml`; granian target is `backend.main:app`; adds `[tool.pgdevkit]` (`env_prefix = "APP_"`) and `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`)
9. Writes `docker-compose.yml` with a single `db` service (Postgres 17) + named volume — this is the **dev** database; pgdevkit's `pgdb testdb` manages a separate, per-branch database for tests
10. Writes `database/.gitkeep` (schema-as-code root — see [pgdevkit's skill](https://github.com/bmsuisse/pgdevkit) for the layer/object-type folder convention) and `tests/conftest.py` + `tests/test_health.py` wired to pgdevkit's `ensure_testdb()` fixture
11. Writes a root `justfile` (`install`, `db-up`, `db-down`, `backend`, `frontend`, `dev`, `generate-api`, `test`) as the project's task runner — `generate-api` runs `backend/dump_openapi.py` then `bun run generate-api`
12. Writes `.env.example` (frontend + backend, `APP_POSTGRES_*` vars), root `.gitignore` (includes `.claude/skills/`, `.agents/skills/`, `.agent/skills/` — skillup-managed, see Step 3; does **not** ignore `frontend/openapi.json` or `frontend/src/lib/generated/` — both are committed), `README.md` with startup steps

After running:

```bash
cd <project-name>
just install                      # uv sync + bun install
just db-up                        # start Postgres
just generate-api                 # dump OpenAPI schema + generate the typed client (needed before frontend builds)
just dev                          # FastAPI (:8000) + Vite (:5173) together
```

## Step 2: Set up code formatting with prek

After scaffolding, run `/prek` to configure formatters for the whole project.
This writes `prek.toml` and `scripts/check_files.py` (a file-size + forbidden-pattern
guard, always included), updates root `pyproject.toml`, adds `.prettierrc`, installs
the git pre-commit hook, and formats all existing files. The project has both
Python (`backend/`) and TypeScript (`frontend/`) so prek will configure both
ruff and prettier automatically.

## Step 3: Install companion skills with skillup

Use [`skillup`](https://github.com/bmsuisse/skillup) — not the plugin marketplace, not `npx skills add` — to give the agent deep, versioned knowledge of the stack:

```bash
uv tool install skillup   # once per machine; skip if already installed

skillup add bmsuisse/skills --skill tanstack-best-practices --skill coding-guidelines-typescript --skill coding-guidelines-python --skill fastapi-guideline --skill autoresearch
skillup add bmsuisse/pgdevkit --skill pgdevkit
skillup add bmsuisse/devtools --skill bmsdna-devtools
```

This installs:

- `tanstack-best-practices` — TanStack Router + Query patterns, SSR integration, query key factories
- `coding-guidelines-typescript` — TypeScript strictness, discriminated unions, async typing
- `coding-guidelines-python` — FastAPI/backend Python standards, ty type checking
- `fastapi-guideline` — Production FastAPI patterns (CRUD, DI, auth, async)
- `autoresearch` — Autonomous experiment loop for iterative improvements
- `pgdevkit` — the Postgres conventions this scaffold's backend already follows (`pgdevkit.db`'s psycopg CRUD helpers, the `database/` schema-as-code folder, `pgdb testdb` for tests). **Always install this one whenever the project touches Postgres** — `backend/db.py` and `database/` are built directly on it, not a loose suggestion.
- `bmsdna-devtools` — the `bdt` CLI (PR status/create, worktrees, commits, Azure logs); prefer it over raw `git`/`az`/`gh` once installed

`skillup add` writes real copies into `.claude/skills/`, `.agents/skills/`, and `.agent/skills/` (one per agent runtime) and pins commit SHAs in `.agents/skills.lock.json`. The scaffold's `.gitignore` already excludes the three `skills/` directories — commit only the lock file, and run `skillup sync` to restore on a new machine.

---

## Reference files (load as needed, not all at once)

| File                                                                     | When to read                                                                 |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| [`references/react-tanstack.md`](references/react-tanstack.md)           | TanStack Router (typed routes, search params, loaders) + Query (caching, mutations) + Zustand patterns |
| [`references/shadcn-ui.md`](references/shadcn-ui.md)                     | Adding shadcn components, theme tokens, `cn()` usage, dark mode              |
| [`references/postgres-pgdevkit.md`](references/postgres-pgdevkit.md)     | `pgdevkit.db` pool lifecycle, CRUD helpers, `.sql` file loading, `database/` folder, `pgdb testdb` for tests |
| [`references/openapi-typed-client.md`](references/openapi-typed-client.md) | Regenerating the SDK/hooks/validators from FastAPI, using the generated client |
| [`references/fastapi-sse.md`](references/fastapi-sse.md)                 | Adding SSE streaming endpoints (AI chat, live updates, logs)                 |

For UI aesthetics — sidebar/nav layout, brand colors, background/surface scale,
border-radius scale, typography, and data grid styling — use the
[`bms-frontend-design`](../bms-frontend-design/) skill. It encodes the actual
BMS visual identity (left nav, BMS red, minimal zebra grids) and supersedes
generic "pick a bold, unique look" aesthetic advice for BMS internal apps,
where the goal is consistency across apps rather than differentiation.

---

## Key conventions

- Always use **just** (not npm scripts / Makefiles / raw commands) as the task runner — run `just <recipe>` for anything the `justfile` covers. Add new recipes to the `justfile` instead of documenting one-off shell commands.
- Always use **bun** (not npm/yarn/pnpm) for the frontend.
- Always use **uv** (not pip/poetry/pipenv) for the backend. Pin Python **3.14**.
- Backend uses `fastapi` + `granian` — do **not** use `fastapi[standard]` (bundles uvicorn, conflicts with Granian).
- Run backend dev with `just backend` (wraps `uv run dev` → `granian --interface asgi main:app --reload`).
- **Do not use SQLAlchemy or any ORM.** Postgres access goes through [pgdevkit](https://github.com/bmsuisse/pgdevkit) (psycopg) — install its skill via `skillup add bmsuisse/pgdevkit --skill pgdevkit` (Step 3) before doing any nontrivial database work, it's the source of truth for these conventions, not this bullet list.
  ```python
  from backend.db import pool
  from pgdevkit.db import pg_retrieve

  async with pool.connection() as conn:
      user = await pg_retrieve(conn, UserRow, {"id": user_id})
  ```
  Simple CRUD uses `pgdevkit.db`'s `pg_*` helpers (named `%(name)s` params, never positional or f-string SQL). Anything with joins/CTEs/aggregations gets its own `.sql` file under `backend/db/queries/`, loaded via `pgdevkit.db.SqlLoader`. The schema itself lives as `.sql` files under `database/` (see [`references/postgres-pgdevkit.md`](references/postgres-pgdevkit.md)) — `pgdb testdb` applies it for tests, a human applies it to production.
- Frontend routing: **file-based** via `@tanstack/router-plugin` — add files under `src/routes/`, route tree is auto-generated.
- Data fetching: **TanStack Query** only — do not roll `useEffect + fetch`. Use `queryOptions` for reusable query definitions.
- Forms: **TanStack Form** (`@tanstack/react-form`) — use `useForm` + `form.Field` with shadcn input/label primitives. Do not add react-hook-form.
- Tables: **TanStack Table** (`@tanstack/react-table`) — headless; you own the markup. Use `useReactTable` + `getCoreRowModel()`.
- Long lists: **TanStack Virtual** (`@tanstack/react-virtual`) — use `useVirtualizer` when rendering 100+ rows.
- Client state: start with `useState` + Context. Reach for **Zustand** only when syncing across distant components. Never Redux.
- URL state (filters, pagination, sort): put in TanStack Router search params with Zod validation, not in Zustand.
- UI components: **shadcn/ui** — generated into `src/components/ui/` via `bunx --bun shadcn@latest add <component>`. Do not install a MUI/Chakra/Mantine. Style with Tailwind v4 tokens (`bg-background`, `text-foreground`, `text-muted-foreground`, `border-border`) — not raw palette colors like `bg-neutral-800`.
- Use the `cn()` helper from `@/lib/utils` to conditionally merge Tailwind classes. Imports use the `@/*` alias (configured in `vite.config.ts` + both tsconfigs).
- Regenerate the typed client after backend model/route changes: `just generate-api` (dumps the OpenAPI schema by importing the app directly, then runs `@hey-api/openapi-ts` — does **not** require the backend running). Commit the resulting `frontend/openapi.json` and `frontend/src/lib/generated/` — they're the reviewable contract, not a build artifact.
- Data fetching against the backend uses the generated SDK/query-options (`src/lib/generated/sdk.gen.ts`, `src/lib/generated/@tanstack/react-query.gen.ts`) — do not hand-write `fetch()` calls or duplicate request/response types; see [`references/openapi-typed-client.md`](references/openapi-typed-client.md).
- CORS is pre-configured for the project's assigned frontend port (seeded from project name). Update for production.
- Typing on backend: `uv add --dev ty` and run `uv run ty check`.
- Run backend tests with `just test` — `tests/conftest.py`'s `ensure_testdb()` fixture applies `database/` to a per-branch test database automatically; no manual container setup.
- Once [`bmsdna-devtools`](https://github.com/bmsuisse/devtools) is installed (Step 3), prefer its `bdt` CLI (`bdt pr create`, `bdt pr status --wait`, `bdt worktree`, `bdt commit`) over raw `git`/`az`/`gh` for PRs, worktrees, and commits.
