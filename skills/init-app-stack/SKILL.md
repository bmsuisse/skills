---
name: init-app-stack
plugin: coding
description: Use this skill whenever the user wants to bootstrap, scaffold, or initialize a new full-stack app with a Nuxt + Nuxt UI frontend and a FastAPI backend. Triggers on requests like "create a new app", "set up a project", "scaffold a full-stack app", "init a new project", or anything involving starting a fresh Nuxt/FastAPI application from scratch.
---

# Init App Stack

Bootstrap a full-stack project with:

- **Frontend**: Nuxt (latest) + Nuxt UI v4 + TailwindCSS, managed with **bun**
- **Backend**: FastAPI, managed with **uv**

## Step 1: Run the scaffold script

This creates the full project structure deterministically — do not scaffold manually.

```bash
uv run python scripts/create.py <project-name>
```

The script (works on Mac, Linux, Windows):

1. Runs `bunx nuxi@latest init frontend --package-manager bun`
2. Installs `@nuxt/ui tailwindcss`, configures `nuxt.config.ts`, `assets/css/main.css`, and `app.vue`
3. Runs `uv init` + `uv add "fastapi[standard]"` in `backend/`
4. Writes a minimal `main.py` with CORS configured for `localhost:3000`
5. Adds `dev = "granian --interface asgi main:app --reload"` and `start = "granian --interface asgi main:app --workers 4"` to `pyproject.toml`
6. Writes a root `.gitignore`

After running:

- **Frontend**: `cd <project-name>/frontend && bun run dev`
- **Backend**: `cd <project-name>/backend && uv run dev`

## Step 2: Install companion skills

Run this once after scaffolding to give the agent deep knowledge of the stack:

```bash
uv run python scripts/install-skills.py
```

Installs into `.agents/skills/`, `.agent/skills/`, and `.claude/skills/`:

- `nuxt-ui` — Nuxt UI v4 components, theming, composables
- `nuxt` — Nuxt framework (routing, data fetching, SSR, server routes)
- `frontend-design` — Anthropic's design aesthetics guide
- `fastapi-templates` — Production FastAPI patterns (CRUD, DI, auth, async)

---

## Reference files (load as needed, not all at once)

| File                                                                 | When to read                                                   |
| -------------------------------------------------------------------- | -------------------------------------------------------------- |
| [`references/nuxt-ui.md`](references/nuxt-ui.md)                     | Working on frontend components, theming, forms, overlays       |
| [`references/nuxt.md`](references/nuxt.md)                           | Routing, data fetching, server routes, SSR, deployment         |
| [`references/fastapi-templates.md`](references/fastapi-templates.md) | Backend structure, CRUD repos, dependency injection, auth      |
| [`references/fastapi-sse.md`](references/fastapi-sse.md)             | Adding SSE streaming endpoints (AI chat, live updates, logs)   |
| [`references/frontend-design.md`](references/frontend-design.md)     | UI aesthetics, typography, color, motion — avoid generic looks |

---

## Key conventions

- Always use **bun** (not npm/yarn/pnpm) for the frontend.
- Always use **uv** (not pip/poetry/pipenv) for the backend.
- Use `fastapi` + `granian` — do **not** use `fastapi[standard]` (bundles uvicorn, which conflicts with Granian).
- Run the backend dev server with `uv run dev` (which calls `granian --interface asgi main:app --reload`).
- Nuxt UI v4 uses TailwindCSS v4 — do not install `@tailwindcss/vite` or tweak Vite config manually.
- Use semantic color utilities (`text-default`, `bg-elevated`, `border-muted`) — not raw Tailwind palette colors.
- CORS is pre-configured for `http://localhost:3000` (Nuxt default). Update for production.
- If typing is needed on backend: `uv add --dev pyright` and run `uv run pyright`.
