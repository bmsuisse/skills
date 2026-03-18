---
name: init-app-stack
description: Use this skill whenever the user wants to bootstrap, scaffold, or initialize a new full-stack app with a Nuxt + Nuxt UI frontend and a FastAPI backend. Triggers on requests like "create a new app", "set up a project", "scaffold a full-stack app", "init a new project", or anything involving starting a fresh Nuxt/FastAPI application from scratch.
---

# Init App Stack

Bootstrap a full-stack project with:
- **Frontend**: Nuxt (latest) + Nuxt UI v4 + TailwindCSS, managed with **bun**
- **Backend**: FastAPI, managed with **uv**

## Project Structure

The target layout is:

```
<project-name>/
├── frontend/          ← Nuxt + Nuxt UI (bun)
└── backend/           ← FastAPI (uv)
```

If the user is already inside a project directory, scaffold `frontend/` and `backend/` there. Otherwise, create a root folder named after the project first.

---

## Step 1: Get the Project Name

Ask for the project name if not already provided. Use it for the root directory. Confirm before proceeding.

---

## Step 2: Bootstrap the Frontend

```bash
# From the project root
bunx nuxi@latest init frontend --package-manager bun
cd frontend

# Install Nuxt UI and TailwindCSS
bun add @nuxt/ui tailwindcss
```

### Configure `nuxt.config.ts`

Update (or create) `frontend/nuxt.config.ts`:

```ts
export default defineNuxtConfig({
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
})
```

### Create the global CSS file

Create `frontend/assets/css/main.css`:

```css
@import "tailwindcss";
@import "@nuxt/ui";
```

### Wrap the app with `<UApp>`

Update `frontend/app.vue` (or the root layout) to wrap content with `<UApp>`:

```vue
<template>
  <UApp>
    <NuxtPage />
  </UApp>
</template>
```

---

## Step 3: Bootstrap the Backend

```bash
# From the project root
mkdir backend && cd backend

# Initialize uv project
uv init .

# Add FastAPI with the standard extras (includes uvicorn)
uv add "fastapi[standard]"
```

### Create the entry point

Replace the generated `main.py` with a minimal FastAPI app:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

### Add a dev run script

Add to `backend/pyproject.toml` under `[tool.uv.scripts]` (or equivalent):

```toml
[tool.uv.scripts]
dev = "fastapi dev main.py"
```

So the backend can be started with `uv run dev`.

---

## Step 4: Add a Root `.gitignore`

Create a `.gitignore` at the project root (if it doesn't exist) covering both stacks:

```
# Node / Bun
node_modules/
.nuxt/
.output/
dist/

# Python / uv
__pycache__/
*.pyc
.venv/
*.egg-info/

# Env
.env
.env.*
!.env.example
```

---

## Step 5: Confirm and Summarize

After scaffolding, tell the user:
- How to start the **frontend**: `cd frontend && bun run dev`
- How to start the **backend**: `cd backend && uv run dev`
- The full directory layout

Point out any manual steps required (e.g., adding a `.env.example` for API base URLs).

---

## Notes

- Always use `bun` (not npm/yarn/pnpm) for the frontend.
- Always use `uv` (not pip/poetry/pipenv) for the backend.
- Use `fastapi[standard]` which bundles `uvicorn` — do not add uvicorn separately.
- Nuxt UI v4 requires TailwindCSS v4 (installed alongside `@nuxt/ui`). Do not install `@tailwindcss/vite` or tweak vite config manually — Nuxt UI's module handles this.
- If the user requests TypeScript for the backend, use `pyright` for type checking (`uv add --dev pyright`).
