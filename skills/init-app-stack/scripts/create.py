#!/usr/bin/env python3
"""
create.py — cross-platform project scaffolding (Mac / Linux / Windows)

Usage:
    uv run python create.py <project-name>

Creates:
    <project-name>/
        frontend/            Vite + React + TanStack Router/Query + Zustand (bun)
        backend/             FastAPI + asyncpg, Python 3.14 (uv)
        docker-compose.yml   Postgres 17 dev service
"""

import subprocess
import sys
import textwrap
from pathlib import Path


def run(cmd: list[str], cwd: Path, label: str) -> None:
    print(f"  → {label}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"❌ Failed: {label}", file=sys.stderr)
        sys.exit(result.returncode)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python create.py <project-name>", file=sys.stderr)
        sys.exit(1)

    project = sys.argv[1]
    root = Path.cwd() / project
    fe = root / "frontend"
    be = root / "backend"

    root.mkdir(exist_ok=True)

    # ── Frontend ──────────────────────────────────────────────────────────────
    print("\n📦 Frontend: Vite + React + TanStack + Zustand")

    run(
        ["bun", "create", "vite@latest", "frontend", "--template", "react-ts"],
        root,
        "bun create vite (react-ts)",
    )
    run(["bun", "install"], fe, "bun install")
    run(
        [
            "bun", "add",
            "@tanstack/react-router",
            "@tanstack/react-query",
            "zustand",
            "zod",
            "class-variance-authority",
            "clsx",
            "tailwind-merge",
            "lucide-react",
            "tw-animate-css",
        ],
        fe,
        "bun add (tanstack, zustand, zod, shadcn deps)",
    )
    run(
        [
            "bun", "add", "-d",
            "@tanstack/router-plugin",
            "@tanstack/react-router-devtools",
            "@tanstack/react-query-devtools",
            "openapi-typescript",
            "tailwindcss",
            "@tailwindcss/vite",
            "@types/node",
        ],
        fe,
        "bun add -d (router-plugin, devtools, openapi-typescript, tailwindcss, @types/node)",
    )

    # vite.config.ts — path alias `@/*` → `src/*` (required by shadcn)
    write(
        fe / "vite.config.ts",
        """\
        import path from 'node:path'
        import { defineConfig } from 'vite'
        import react from '@vitejs/plugin-react'
        import { TanStackRouterVite } from '@tanstack/router-plugin/vite'
        import tailwindcss from '@tailwindcss/vite'

        export default defineConfig({
          plugins: [
            TanStackRouterVite({ target: 'react', autoCodeSplitting: true }),
            react(),
            tailwindcss(),
          ],
          resolve: {
            alias: {
              '@': path.resolve(__dirname, './src'),
            },
          },
          server: { port: 5173 },
        })
        """,
    )

    # src/index.css — Tailwind v4 + shadcn theme (neutral base, OKLCH vars)
    write(
        fe / "src" / "index.css",
        """\
        @import "tailwindcss";
        @import "tw-animate-css";

        @custom-variant dark (&:is(.dark *));

        :root {
          --radius: 0.625rem;
          --background: oklch(1 0 0);
          --foreground: oklch(0.145 0 0);
          --card: oklch(1 0 0);
          --card-foreground: oklch(0.145 0 0);
          --popover: oklch(1 0 0);
          --popover-foreground: oklch(0.145 0 0);
          --primary: oklch(0.205 0 0);
          --primary-foreground: oklch(0.985 0 0);
          --secondary: oklch(0.97 0 0);
          --secondary-foreground: oklch(0.205 0 0);
          --muted: oklch(0.97 0 0);
          --muted-foreground: oklch(0.556 0 0);
          --accent: oklch(0.97 0 0);
          --accent-foreground: oklch(0.205 0 0);
          --destructive: oklch(0.577 0.245 27.325);
          --border: oklch(0.922 0 0);
          --input: oklch(0.922 0 0);
          --ring: oklch(0.708 0 0);
        }

        .dark {
          --background: oklch(0.145 0 0);
          --foreground: oklch(0.985 0 0);
          --card: oklch(0.205 0 0);
          --card-foreground: oklch(0.985 0 0);
          --popover: oklch(0.205 0 0);
          --popover-foreground: oklch(0.985 0 0);
          --primary: oklch(0.922 0 0);
          --primary-foreground: oklch(0.205 0 0);
          --secondary: oklch(0.269 0 0);
          --secondary-foreground: oklch(0.985 0 0);
          --muted: oklch(0.269 0 0);
          --muted-foreground: oklch(0.708 0 0);
          --accent: oklch(0.269 0 0);
          --accent-foreground: oklch(0.985 0 0);
          --destructive: oklch(0.704 0.191 22.216);
          --border: oklch(1 0 0 / 10%);
          --input: oklch(1 0 0 / 15%);
          --ring: oklch(0.556 0 0);
        }

        @theme inline {
          --radius-sm: calc(var(--radius) - 4px);
          --radius-md: calc(var(--radius) - 2px);
          --radius-lg: var(--radius);
          --radius-xl: calc(var(--radius) + 4px);

          --color-background: var(--background);
          --color-foreground: var(--foreground);
          --color-card: var(--card);
          --color-card-foreground: var(--card-foreground);
          --color-popover: var(--popover);
          --color-popover-foreground: var(--popover-foreground);
          --color-primary: var(--primary);
          --color-primary-foreground: var(--primary-foreground);
          --color-secondary: var(--secondary);
          --color-secondary-foreground: var(--secondary-foreground);
          --color-muted: var(--muted);
          --color-muted-foreground: var(--muted-foreground);
          --color-accent: var(--accent);
          --color-accent-foreground: var(--accent-foreground);
          --color-destructive: var(--destructive);
          --color-border: var(--border);
          --color-input: var(--input);
          --color-ring: var(--ring);
        }

        @layer base {
          * {
            @apply border-border outline-ring/50;
          }
          body {
            @apply bg-background text-foreground;
          }
        }
        """,
    )

    # src/main.tsx — QueryClientProvider + RouterProvider
    write(
        fe / "src" / "main.tsx",
        """\
        import { StrictMode } from 'react'
        import { createRoot } from 'react-dom/client'
        import { QueryClientProvider } from '@tanstack/react-query'
        import { RouterProvider, createRouter } from '@tanstack/react-router'
        import { queryClient } from './lib/queryClient'
        import { routeTree } from './routeTree.gen'
        import './index.css'

        const router = createRouter({
          routeTree,
          context: { queryClient },
          defaultPreload: 'intent',
        })

        declare module '@tanstack/react-router' {
          interface Register {
            router: typeof router
          }
        }

        createRoot(document.getElementById('root')!).render(
          <StrictMode>
            <QueryClientProvider client={queryClient}>
              <RouterProvider router={router} />
            </QueryClientProvider>
          </StrictMode>,
        )
        """,
    )

    # src/lib/queryClient.ts
    write(
        fe / "src" / "lib" / "queryClient.ts",
        """\
        import { QueryClient } from '@tanstack/react-query'

        export const queryClient = new QueryClient({
          defaultOptions: {
            queries: {
              staleTime: 30_000,
              refetchOnWindowFocus: false,
            },
          },
        })
        """,
    )

    # src/lib/api.ts — typed fetch wrapper
    write(
        fe / "src" / "lib" / "api.ts",
        """\
        const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

        export async function api<T>(path: string, init?: RequestInit): Promise<T> {
          const res = await fetch(`${BASE}${path}`, {
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
            ...init,
          })
          if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
          return res.json() as Promise<T>
        }
        """,
    )

    # src/lib/utils.ts — shadcn `cn` helper
    write(
        fe / "src" / "lib" / "utils.ts",
        """\
        import { clsx, type ClassValue } from 'clsx'
        import { twMerge } from 'tailwind-merge'

        export function cn(...inputs: ClassValue[]) {
          return twMerge(clsx(inputs))
        }
        """,
    )

    # components.json — shadcn CLI config
    write(
        fe / "components.json",
        """\
        {
          "$schema": "https://ui.shadcn.com/schema.json",
          "style": "new-york",
          "rsc": false,
          "tsx": true,
          "tailwind": {
            "config": "",
            "css": "src/index.css",
            "baseColor": "neutral",
            "cssVariables": true,
            "prefix": ""
          },
          "aliases": {
            "components": "@/components",
            "utils": "@/lib/utils",
            "ui": "@/components/ui",
            "lib": "@/lib",
            "hooks": "@/hooks"
          },
          "iconLibrary": "lucide"
        }
        """,
    )

    # src/routes/__root.tsx
    write(
        fe / "src" / "routes" / "__root.tsx",
        """\
        import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
        import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
        import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
        import type { QueryClient } from '@tanstack/react-query'

        export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
          component: RootLayout,
        })

        function RootLayout() {
          return (
            <>
              <Outlet />
              <TanStackRouterDevtools />
              <ReactQueryDevtools buttonPosition="bottom-left" />
            </>
          )
        }
        """,
    )

    # src/routes/index.tsx — sample route using Query + shadcn tokens
    write(
        fe / "src" / "routes" / "index.tsx",
        """\
        import { createFileRoute } from '@tanstack/react-router'
        import { useQuery } from '@tanstack/react-query'
        import { api } from '@/lib/api'
        import { cn } from '@/lib/utils'

        export const Route = createFileRoute('/')({
          component: Home,
        })

        function Home() {
          const { data, isLoading } = useQuery({
            queryKey: ['health'],
            queryFn: () => api<{ status: string }>('/health'),
          })

          return (
            <main className="mx-auto max-w-2xl p-8">
              <h1 className="text-3xl font-semibold tracking-tight">Hello</h1>
              <p className={cn('mt-2 text-muted-foreground')}>
                Backend: {isLoading ? '…' : data?.status ?? 'unreachable'}
              </p>
              <p className="mt-6 text-sm text-muted-foreground">
                Add shadcn components: <code>bunx --bun shadcn@latest add button</code>
              </p>
            </main>
          )
        }
        """,
    )

    # src/stores/.gitkeep — placeholder for Zustand stores
    write(
        fe / "src" / "stores" / ".gitkeep",
        "",
    )

    # Replace stock App.tsx/App.css (not used; router owns render tree)
    for stale in ("src/App.tsx", "src/App.css"):
        p = fe / stale
        if p.exists():
            p.unlink()

    # tsconfig.json + tsconfig.app.json — add `@/*` path alias (required by shadcn)
    # Stock Vite tsconfigs may include // comments; use a tolerant loader.
    import json
    import re

    def load_jsonc(p: Path) -> dict:
        raw = p.read_text(encoding="utf-8")
        stripped = re.sub(r"//[^\n]*", "", raw)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)
        return json.loads(stripped)

    def patch_tsconfig_paths(p: Path) -> None:
        if not p.exists():
            return
        data = load_jsonc(p)
        co = data.setdefault("compilerOptions", {})
        # TS 5.4+ resolves `paths` relative to the tsconfig; no `baseUrl` needed
        # (and baseUrl is deprecated in TS 6.0).
        paths = co.setdefault("paths", {})
        paths["@/*"] = ["./src/*"]
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    patch_tsconfig_paths(fe / "tsconfig.json")
    patch_tsconfig_paths(fe / "tsconfig.app.json")

    # package.json — fix build order (routeTree.gen.ts needs `vite build` first,
    # then type-check) + add generate-api script
    pkg = fe / "package.json"
    if pkg.exists():
        data = json.loads(pkg.read_text(encoding="utf-8"))
        scripts = data.setdefault("scripts", {})
        scripts["build"] = "vite build && tsc --noEmit"
        scripts["generate-api"] = (
            "openapi-typescript http://localhost:8000/openapi.json -o src/lib/api-types.ts"
        )
        pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Frontend .env.example
    write(
        fe / ".env.example",
        """\
        VITE_API_URL=http://localhost:8000
        """,
    )

    print("✅ Frontend ready")

    # ── Backend ───────────────────────────────────────────────────────────────
    print("\n🐍 Backend: FastAPI + asyncpg (Python 3.14)")

    be.mkdir(exist_ok=True)
    run(["uv", "init", "--python", "3.14", "."], be, "uv init (python 3.14)")
    run(
        ["uv", "add", "fastapi", "granian[reload]", "asyncpg", "pydantic-settings"],
        be,
        "uv add fastapi granian[reload] asyncpg pydantic-settings",
    )

    # config.py
    write(
        be / "config.py",
        """\
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class Settings(BaseSettings):
            model_config = SettingsConfigDict(env_file=".env", extra="ignore")

            database_url: str = "postgresql://postgres:postgres@localhost:5432/app"
            cors_origins: list[str] = ["http://localhost:5173"]

        settings = Settings()
        """,
    )

    # db.py — asyncpg pool + t-string sql() helper (PEP 750)
    write(
        be / "db.py",
        '''\
        """Asyncpg pool + t-string SQL helper (PEP 750, Python 3.14)."""
        from __future__ import annotations

        import asyncpg
        from string.templatelib import Template

        from config import settings

        pool: asyncpg.Pool | None = None


        async def connect() -> None:
            global pool
            pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)


        async def disconnect() -> None:
            global pool
            if pool is not None:
                await pool.close()
                pool = None


        def sql(template: Template) -> tuple[str, list[object]]:
            """Convert a PEP 750 t-string into (query, params) for asyncpg.

            Usage:
                query, params = sql(t"SELECT * FROM users WHERE id = {user_id}")
                row = await conn.fetchrow(query, *params)

            Interpolated values become positional params ($1, $2, ...).
            Literal parts pass through unchanged. Safe from SQL injection —
            values never touch string concatenation.
            """
            parts: list[str] = []
            params: list[object] = []
            for item in template:
                if isinstance(item, str):
                    parts.append(item)
                else:  # Interpolation
                    params.append(item.value)
                    parts.append(f"${len(params)}")
            return "".join(parts), params
        ''',
    )

    # main.py — FastAPI with lifespan-managed pool
    write(
        be / "main.py",
        """\
        from contextlib import asynccontextmanager
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        from config import settings
        from db import connect, disconnect, pool, sql


        @asynccontextmanager
        async def lifespan(_: FastAPI):
            await connect()
            yield
            await disconnect()


        app = FastAPI(title="Backend API", version="0.1.0", lifespan=lifespan)

        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


        @app.get("/health")
        async def health() -> dict:
            assert pool is not None
            async with pool.acquire() as conn:
                query, params = sql(t"SELECT 1 AS ok")
                row = await conn.fetchrow(query, *params)
            return {"status": "ok", "db": row["ok"] == 1}
        """,
    )

    # scripts.py — tiny wrappers so `uv run dev` / `uv run start` work via
    # [project.scripts] entry points (uv has no native shell-command aliases).
    write(
        be / "scripts.py",
        """\
        import subprocess
        import sys


        def dev() -> None:
            sys.exit(subprocess.call(["granian", "--interface", "asgi", "main:app", "--reload"]))


        def start() -> None:
            sys.exit(subprocess.call(["granian", "--interface", "asgi", "main:app", "--workers", "4"]))
        """,
    )

    # Append build-system + [project.scripts] so `uv run dev` / `uv run start` work.
    # Needs: a build backend (setuptools), explicit py-modules (flat layout),
    # and tool.uv.package = true so uv installs the project's entry points.
    pyproject = be / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[project.scripts]" not in content:
            content += textwrap.dedent(
                """
                [project.scripts]
                dev = "scripts:dev"
                start = "scripts:start"

                [build-system]
                requires = ["setuptools>=61"]
                build-backend = "setuptools.build_meta"

                [tool.setuptools]
                py-modules = ["main", "db", "config", "scripts"]

                [tool.uv]
                package = true
                """
            )
            pyproject.write_text(content, encoding="utf-8")
        run(["uv", "sync"], be, "uv sync (install entry points)")

    # Backend .env.example
    write(
        be / ".env.example",
        """\
        DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app
        CORS_ORIGINS=["http://localhost:5173"]
        """,
    )

    # Drop default hello.py if uv init created it
    hello = be / "hello.py"
    if hello.exists():
        hello.unlink()

    print("✅ Backend ready")

    # ── docker-compose.yml (Postgres) ─────────────────────────────────────────
    write(
        root / "docker-compose.yml",
        """\
        services:
          db:
            image: postgres:17-alpine
            restart: unless-stopped
            environment:
              POSTGRES_USER: postgres
              POSTGRES_PASSWORD: postgres
              POSTGRES_DB: app
            ports:
              - "5432:5432"
            volumes:
              - pgdata:/var/lib/postgresql/data
            healthcheck:
              test: ["CMD-SHELL", "pg_isready -U postgres"]
              interval: 5s
              timeout: 3s
              retries: 10

        volumes:
          pgdata:
        """,
    )

    # ── Root .gitignore ───────────────────────────────────────────────────────
    write(
        root / ".gitignore",
        """\
        # Node / Bun
        node_modules/
        dist/
        .bun/
        frontend/src/routeTree.gen.ts
        frontend/src/lib/api-types.ts

        # Python / uv
        __pycache__/
        *.pyc
        .venv/
        *.egg-info/
        .python-version

        # Env
        .env
        .env.*
        !.env.example
        """,
    )

    # ── README.md ─────────────────────────────────────────────────────────────
    write(
        root / "README.md",
        f"""\
        # {project}

        Full-stack app: Vite + React + TanStack (Router/Query) + Zustand on the frontend,
        FastAPI + asyncpg on the backend, Postgres 17 in Docker.

        ## Dev

        ```bash
        cp frontend/.env.example frontend/.env
        cp backend/.env.example  backend/.env

        docker compose up -d db                 # Postgres on :5432
        (cd backend  && uv run dev)             # FastAPI on :8000
        (cd frontend && bun run dev)            # Vite on :5173
        ```

        ## Regenerate typed API client

        With the backend running:

        ```bash
        cd frontend && bun run generate-api
        ```

        Writes `frontend/src/lib/api-types.ts` from `/openapi.json`.

        ## Stack notes

        - No ORM. Raw SQL via `db.sql()` — PEP 750 t-strings → asyncpg `$1, $2` params.
        - File-based routing: add files under `frontend/src/routes/`.
        - Client state: `useState` + Context first. Zustand only when crossing distant components.
        - URL state (filters, pagination): TanStack Router search params, not Zustand.
        """,
    )

    print(f"""
🎉 Project '{project}' is ready!

  docker compose up -d db
  cd {project}/backend  && uv run dev
  cd {project}/frontend && bun run dev
""")


if __name__ == "__main__":
    main()
