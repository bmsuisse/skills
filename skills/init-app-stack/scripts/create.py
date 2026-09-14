#!/usr/bin/env python3
"""
create.py — cross-platform project scaffolding (Mac / Linux / Windows)

Usage:
    uv run python create.py <project-name>

Creates:
    <project-name>/
        frontend/            Vite + React + TanStack Router/Query + Zustand (bun)
        backend/             FastAPI + pgdevkit (psycopg), Python 3.14 (uv)
        database/            Schema-as-code, applied by pgdevkit's `pgdb testdb`
        tests/               pytest + pgdevkit's ensure_testdb() fixture
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

    import re
    # Filesystem/state-file-safe slug (agent_preview.py's /tmp state file names) --
    # project names are free text, state file names aren't.
    project_slug = re.sub(r"[^a-z0-9-]+", "-", project.lower()).strip("-") or "app"

    import random
    rng = random.Random(project)  # deterministic per project name
    fe_port = rng.randint(10000, 59999)
    be_port = rng.randint(10000, 59999)
    while be_port == fe_port:
        be_port = rng.randint(10000, 59999)

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
            "@tanstack/react-form",
            "@tanstack/react-table",
            "@tanstack/react-virtual",
            "zustand",
            "zod",
            "@bmsuisse/ui",
            "@bmsuisse/datagrid",
            "class-variance-authority",
            "clsx",
            "tailwind-merge",
            "lucide-react",
            "@heroicons/react",
            "tw-animate-css",
        ],
        fe,
        "bun add (tanstack, zustand, zod, @bmsuisse/ui + @bmsuisse/datagrid, shadcn deps, heroicons)",
    )
    run(
        [
            "bun", "add", "-d",
            "@tanstack/router-plugin",
            "@tanstack/react-devtools",
            "@tanstack/react-router-devtools",
            "@tanstack/react-query-devtools",
            "@hey-api/openapi-ts",
            "tailwindcss",
            "@tailwindcss/vite",
            "@types/node",
        ],
        fe,
        "bun add -d (router-plugin, devtools, @hey-api/openapi-ts, tailwindcss, @types/node)",
    )

    # openapi-ts.config.ts — generates a full SDK (typed fetch functions),
    # TanStack Query options, and Zod runtime validators from openapi.json.
    # The @hey-api/client-fetch runtime is bundled into the generated output
    # (src/lib/generated/client/, core/) — no extra npm dependency needed.
    write(
        fe / "openapi-ts.config.ts",
        """\
        import { defineConfig } from '@hey-api/openapi-ts'

        export default defineConfig({
          client: '@hey-api/client-fetch',
          input: './openapi.json',
          output: {
            path: './src/lib/generated',
            postProcess: ['prettier'],
          },
          plugins: ['@tanstack/react-query', 'zod', { name: '@hey-api/sdk', validator: { request: 'zod' } }],
        })
        """,
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
          server: { port: __FE_PORT__ },
        })
        """.replace("__FE_PORT__", str(fe_port)),
    )

    # src/index.css — Tailwind v4 + shadcn theme (neutral base, OKLCH vars)
    write(
        fe / "src" / "index.css",
        """\
        @import "tailwindcss";
        @import "tw-animate-css";

        /* @bmsuisse/ui and @bmsuisse/datagrid ship compiled JS with Tailwind
           utility classes baked into their dist output. Tailwind v4 does not
           scan node_modules by default, so without these @source lines their
           components render structurally but completely unstyled. */
        @source "../node_modules/@bmsuisse/ui/dist/**/*.js";
        @source "../node_modules/@bmsuisse/datagrid/dist/**/*.js";

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
        import './lib/api'
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

    # src/lib/api.ts — configures the generated hey-api client (base URL, cookies).
    # Imported once for its side effect (see main.tsx) before any query runs.
    # Does not exist as a usable module until `just generate-api` has run once
    # (it imports from ./generated, which is codegen output).
    write(
        fe / "src" / "lib" / "api.ts",
        """\
        import { client } from './generated/client.gen'

        client.setConfig({
          baseUrl: import.meta.env.VITE_API_URL ?? 'http://localhost:__BE_PORT__',
          credentials: 'include',
        })
        """.replace("__BE_PORT__", str(be_port)),
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
        import { TanStackDevtools } from '@tanstack/react-devtools'
        import { ReactQueryDevtoolsPanel } from '@tanstack/react-query-devtools'
        import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools'
        import type { QueryClient } from '@tanstack/react-query'

        export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
          component: RootLayout,
        })

        function RootLayout() {
          return (
            <>
              <Outlet />
              {import.meta.env.DEV && (
                <TanStackDevtools
                  plugins={[
                    { name: 'TanStack Query', render: <ReactQueryDevtoolsPanel /> },
                    { name: 'TanStack Router', render: <TanStackRouterDevtoolsPanel /> },
                  ]}
                />
              )}
            </>
          )
        }
        """,
    )

    # src/routes/index.tsx — sample route using Query + @bmsuisse/ui components
    write(
        fe / "src" / "routes" / "index.tsx",
        """\
        import { createFileRoute } from '@tanstack/react-router'
        import { useQuery } from '@tanstack/react-query'
        import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@bmsuisse/ui'
        import { healthOptions } from '@/lib/generated/@tanstack/react-query.gen'

        export const Route = createFileRoute('/')({
          component: Home,
        })

        function Home() {
          const { data, isLoading } = useQuery(healthOptions())

          return (
            <main className="mx-auto max-w-2xl p-8">
              <Card>
                <CardHeader>
                  <CardTitle>Hello</CardTitle>
                  <CardDescription>
                    Backend: {isLoading ? '…' : data?.status ?? 'unreachable'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button>Get started</Button>
                </CardContent>
              </Card>
              <p className="mt-6 text-sm text-muted-foreground">
                UI components come from <code>@bmsuisse/ui</code>. For anything it
                doesn't have: <code>bunx --bun shadcn@latest add &lt;component&gt;</code>
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
        scripts["generate-api"] = "openapi-ts"
        pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Frontend .env.example
    write(
        fe / ".env.example",
        """\
        VITE_API_URL=http://localhost:__BE_PORT__
        """.replace("__BE_PORT__", str(be_port)),
    )

    print("✅ Frontend ready")

    # ── Backend ───────────────────────────────────────────────────────────────
    print("\n🐍 Backend: FastAPI + pgdevkit (psycopg), Python 3.14")

    be.mkdir(exist_ok=True)
    run(["uv", "init", "--python", "3.14", "."], root, "uv init (python 3.14)")
    run(
        ["uv", "add", "fastapi", "granian[reload]", "pydantic-settings", "pgdevkit[cli,db]"],
        root,
        "uv add fastapi granian[reload] pydantic-settings pgdevkit[cli,db]",
    )
    run(
        ["uv", "add", "--dev", "pytest", "pytest-asyncio"],
        root,
        "uv add --dev pytest pytest-asyncio",
    )

    # backend/__init__.py — makes `backend` a proper package
    write(be / "__init__.py", "")

    # config.py
    write(
        be / "config.py",
        """\
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class Settings(BaseSettings):
            model_config = SettingsConfigDict(env_file=".env", extra="ignore")

            cors_origins: list[str] = ["http://localhost:__FE_PORT__"]

        settings = Settings()
        """.replace("__FE_PORT__", str(fe_port)),
    )

    # db.py — pgdevkit's PgPool (psycopg). env_prefix must match [tool.pgdevkit]
    # env_prefix + "POSTGRES_" so this pool picks up ensure_testdb()'s env vars
    # under pytest, and the docker-compose Postgres's vars under `just dev`.
    write(
        be / "db.py",
        '''\
        """Postgres access via pgdevkit — no ORM, no hand-rolled pool."""
        from __future__ import annotations

        from pgdevkit.db import PgPool

        pool = PgPool(env_prefix="APP_POSTGRES_")
        ''',
    )

    # main.py — FastAPI with lifespan-managed pool
    write(
        be / "main.py",
        """\
        from contextlib import asynccontextmanager
        from pathlib import Path

        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles

        from backend.config import settings
        from backend.db import pool


        @asynccontextmanager
        async def lifespan(_: FastAPI):
            await pool.open()
            yield
            await pool.close()


        app = FastAPI(title="Backend API", version="0.1.0", lifespan=lifespan)

        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


        @app.get("/health", operation_id="health")
        async def health() -> dict:
            async with pool.connection() as conn:
                cur = await conn.execute("SELECT 1 AS ok")
                row = await cur.fetchone()
            return {"status": "ok", "db": row[0] == 1}


        # Mounted last so the routes above always match first -- serves `bun run
        # build`'s output for `just agent-preview` (single process, one port). Not
        # present during normal `just dev`, since Vite serves the frontend then and
        # frontend/dist won't exist yet.
        _frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
        if _frontend_dist.exists():
            app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
        """,
    )

    # dump_openapi.py — writes the OpenAPI schema to frontend/openapi.json by
    # importing the app object directly (no running server/DB needed, since
    # app.openapi() never touches the lifespan-managed pool). Source input for
    # `bun run generate-api` — see justfile's `generate-api` recipe.
    write(
        be / "dump_openapi.py",
        '''\
        """Dump the FastAPI OpenAPI schema to frontend/openapi.json."""
        import json
        from pathlib import Path

        from backend.main import app

        out = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
        out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
        print(f"OpenAPI schema written to {out}")
        ''',
    )

    # scripts.py — tiny wrappers so `uv run dev` / `uv run start` work via
    # [project.scripts] entry points (uv has no native shell-command aliases).
    # Port is overridable via BACKEND_PORT (see scripts/agent_preview.py and the
    # justfile's `agent-preview` recipe, which set it to an OS-picked free port
    # so concurrent worktrees never collide on __BE_PORT__).
    write(
        be / "scripts.py",
        """\
        import os
        import subprocess
        import sys

        PORT = os.environ.get("BACKEND_PORT", "__BE_PORT__")


        def dev() -> None:
            sys.exit(subprocess.call(["granian", "--interface", "asgi", "backend.main:app", "--port", PORT, "--reload"]))


        def start() -> None:
            sys.exit(subprocess.call(["granian", "--interface", "asgi", "backend.main:app", "--port", PORT, "--workers", "4"]))
        """.replace("__BE_PORT__", str(be_port)),
    )

    # Append build-system + [project.scripts] so `uv run dev` / `uv run start` work.
    # Needs: a build backend (setuptools), explicit py-modules (flat layout),
    # and tool.uv.package = true so uv installs the project's entry points.
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[project.scripts]" not in content:
            content += textwrap.dedent(
                """
                [project.scripts]
                dev = "backend.scripts:dev"
                start = "backend.scripts:start"

                [build-system]
                requires = ["setuptools>=61"]
                build-backend = "setuptools.build_meta"

                [tool.setuptools]
                packages = ["backend"]

                [tool.uv]
                package = true

                [tool.pgdevkit]
                database_dir = "database"
                env_prefix = "APP_"

                [tool.pytest.ini_options]
                testpaths = ["tests"]
                asyncio_mode = "auto"
                """
            )
            pyproject.write_text(content, encoding="utf-8")
        run(["uv", "sync"], root, "uv sync (install entry points)")

    # Root .env.example (backend vars; uv runs from root so .env is at root).
    # APP_POSTGRES_* matches [tool.pgdevkit] env_prefix="APP_" + PgPool's
    # env_prefix="APP_POSTGRES_" in backend/db.py — same vars the docker-compose
    # `db` service exposes, and the shape ensure_testdb() overrides under pytest.
    write(
        root / ".env.example",
        """\
        APP_POSTGRES_HOST=localhost
        APP_POSTGRES_PORT=5432
        APP_POSTGRES_DB=app
        APP_POSTGRES_USER=postgres
        APP_POSTGRES_PASSWORD=postgres
        CORS_ORIGINS=["http://localhost:__FE_PORT__"]
        """.replace("__FE_PORT__", str(fe_port)),
    )

    # Drop default hello.py if uv init created it at root
    hello = root / "hello.py"
    if hello.exists():
        hello.unlink()

    # database/ — schema-as-code, source of truth for the Postgres schema.
    # `pgdb testdb` applies every .sql file here to the local test database;
    # a human applies the same files to production. See pgdevkit's
    # docs/database-layout.md for the layer/object-type folder convention.
    write(root / "database" / ".gitkeep", "")

    # tests/ — pgdevkit's ensure_testdb() spins up a per-branch test database
    # and applies database/ to it before any test runs.
    write(
        root / "tests" / "conftest.py",
        """\
        import os

        import pytest
        from pgdevkit.testdb import ensure_testdb


        @pytest.fixture(scope="session", autouse=True)
        def _testdb_env():
            env = ensure_testdb()
            for key, value in env.items():
                os.environ[key] = value
        """,
    )
    write(
        root / "tests" / "test_health.py",
        """\
        from backend.db import pool


        async def test_db_connection():
            await pool.open()
            try:
                async with pool.connection() as conn:
                    cur = await conn.execute("SELECT 1 AS ok")
                    row = await cur.fetchone()
                assert row[0] == 1
            finally:
                await pool.close()
        """,
    )

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

    # scripts/agent_preview.py — isolated, port-agnostic preview: its own pgdevkit-
    # scoped Postgres database (project + git branch), the frontend built once and
    # served by the backend's StaticFiles mount (see main.py) instead of a separate
    # Vite dev server, and a port picked so it never collides with another
    # worktree/agent's preview or `just dev`. Modeled on OneSales's
    # scripts/agent_preview.py, minus the MS-Entra-auth-bypass bits this scaffold
    # has no equivalent of (no auth here at all yet).
    write(
        root / "scripts" / "agent_preview.py",
        '''\
        """Start (or stop) an isolated, agent-safe preview of the app: its own
        Postgres database (via pgdevkit, scoped to this project + git branch -- see
        pgdevkit.testdb.workspace_db_name), the frontend built once and served by the
        backend (no separate Vite dev server), and a port picked to not collide with
        any other worktree's preview or dev server.

        Why this exists: `just dev` hardcodes ports __BE_PORT__ (backend) and __FE_PORT__
        (frontend) -- multiple concurrent worktrees/agents on the same machine would
        collide on them. This script never touches another process; it always asks
        the OS for a free port first (unless overridden with --port or BACKEND_PORT),
        and always runs against its own isolated database.

        Usage:
            uv run python scripts/agent_preview.py start
            uv run python scripts/agent_preview.py start --rebuild
            uv run python scripts/agent_preview.py start --port 9300
            uv run python scripts/agent_preview.py status
            uv run python scripts/agent_preview.py stop
        """

        from __future__ import annotations

        import argparse
        import json
        import os
        import socket
        import subprocess
        import sys
        import time
        import urllib.error
        import urllib.request
        from pathlib import Path

        REPO_ROOT = Path(__file__).resolve().parents[1]
        PROJECT_SLUG = "__PROJECT_SLUG__"


        def _free_port() -> int:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]


        def _state_path(db_name: str) -> Path:
            # One state file per isolated database -- naturally one per project+branch
            # (see pgdevkit.testdb.workspace_db_name), so two worktrees on different
            # branches never share or clobber each other's file.
            return Path(f"/tmp/{PROJECT_SLUG}-agent-preview-{db_name}.json")


        def _wait_healthy(base_url: str, timeout_s: float = 30.0) -> None:
            deadline = time.monotonic() + timeout_s
            last_error: Exception | None = None
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(f"{base_url}/health", timeout=2) as resp:
                        if resp.status == 200:
                            return
                except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                    last_error = exc
                time.sleep(0.5)
            raise RuntimeError(f"backend never became healthy at {base_url}/health within {timeout_s}s: {last_error}")


        def _pid_alive(pid: int) -> bool:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True  # exists, owned by someone else
            return True


        def cmd_start(args: argparse.Namespace) -> None:
            from pgdevkit.testdb import ensure_testdb, status

            print("Provisioning isolated test database (pgdevkit)...")
            db_env = ensure_testdb()
            db_name = status()["database"]

            state_path = _state_path(db_name)
            if state_path.exists():
                existing = json.loads(state_path.read_text())
                if _pid_alive(existing["pid"]):
                    print(f"Already running: {existing['base_url']} (pid {existing['pid']}). Use `stop` first, or `status`.")
                    return
                state_path.unlink()  # stale -- process died without cleanup

            dist_dir = REPO_ROOT / "frontend" / "dist"
            if args.rebuild or not dist_dir.exists():
                print("Building frontend (bun run build)...")
                result = subprocess.run(["bun", "run", "build"], cwd=REPO_ROOT / "frontend")
                if result.returncode != 0:
                    sys.exit(result.returncode)
            else:
                print(f"Reusing existing build at {dist_dir} (pass --rebuild to force a fresh one).")

            port = args.port or int(os.environ.get("BACKEND_PORT", 0)) or _free_port()
            base_url = f"http://127.0.0.1:{port}"

            env = os.environ.copy()
            env.update(db_env)
            env["BACKEND_PORT"] = str(port)

            log_path = Path(f"/tmp/{PROJECT_SLUG}-agent-preview-{db_name}.log")
            log_file = log_path.open("w")
            print(f"Starting backend on {base_url} (log: {log_path})...")
            proc = subprocess.Popen(
                ["granian", "--interface", "asgi", "backend.main:app", "--port", str(port)],
                cwd=REPO_ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # survives this script exiting
            )

            try:
                _wait_healthy(base_url)
            except RuntimeError:
                proc.terminate()
                print(f"Startup failed -- see {log_path} for backend output.", file=sys.stderr)
                raise

            state_path.write_text(
                json.dumps({"pid": proc.pid, "port": port, "base_url": base_url, "db_name": db_name, "log": str(log_path)})
            )

            print(f"Ready: {base_url}")
            print(f"Isolated database: {db_name}")
            print("Stop with: uv run python scripts/agent_preview.py stop")


        def _load_state() -> tuple[Path, dict] | None:
            from pgdevkit.testdb import status

            db_name = status()["database"]
            state_path = _state_path(db_name)
            if not state_path.exists():
                return None
            return state_path, json.loads(state_path.read_text())


        def cmd_status(_args: argparse.Namespace) -> None:
            found = _load_state()
            if not found:
                print("Not running for this workspace.")
                return
            state_path, state = found
            alive = _pid_alive(state["pid"])
            print(f"{'Running' if alive else 'Stale (process died)'}: {state['base_url']} (pid {state['pid']})")
            print(f"Database: {state['db_name']}")
            print(f"Log: {state['log']}")
            if not alive:
                print(f"Stale state file: {state_path} (cleared by the next `start`)")


        def cmd_stop(_args: argparse.Namespace) -> None:
            found = _load_state()
            if not found:
                print("Not running for this workspace.")
                return
            state_path, state = found
            if _pid_alive(state["pid"]):
                try:
                    os.killpg(state["pid"], 9)
                except ProcessLookupError:
                    pass
                print(f"Stopped pid {state['pid']} ({state['base_url']}).")
            else:
                print("Process already gone.")
            state_path.unlink()


        def main() -> None:
            parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
            sub = parser.add_subparsers(dest="command", required=True)

            p_start = sub.add_parser("start", help="Provision the isolated DB, build if needed, start the backend")
            p_start.add_argument("--rebuild", action="store_true", help="Force `bun run build` even if frontend/dist exists")
            p_start.add_argument("--port", type=int, default=None, help="Use this port instead of an OS-picked free one (or BACKEND_PORT)")
            p_start.set_defaults(func=cmd_start)

            p_status = sub.add_parser("status", help="Show whether a preview is running for this workspace")
            p_status.set_defaults(func=cmd_status)

            p_stop = sub.add_parser("stop", help="Stop the preview running for this workspace, if any")
            p_stop.set_defaults(func=cmd_stop)

            args = parser.parse_args()
            args.func(args)


        if __name__ == "__main__":
            main()
        '''.replace("__PROJECT_SLUG__", project_slug)
        .replace("__BE_PORT__", str(be_port))
        .replace("__FE_PORT__", str(fe_port)),
    )

    # ── justfile (task runner) ────────────────────────────────────────────────
    write(
        root / "justfile",
        """\
        set dotenv-load := true
        set shell := ["bash", "-uc"]

        default:
            @just --list

        # Install all deps (backend + frontend)
        install:
            uv sync
            cd frontend && bun install

        # Start Postgres in the background
        db-up:
            docker compose up -d db

        # Stop Postgres
        db-down:
            docker compose down

        # Run the FastAPI backend (:__BE_PORT__)
        backend:
            uv run dev

        # Run the Vite frontend (:__FE_PORT__)
        frontend:
            cd frontend && bun run dev

        # Run backend + frontend together (Ctrl+C stops both)
        dev:
            trap 'kill 0' EXIT
            just backend & just frontend &
            wait

        # Isolated, port-agnostic preview for agents/parallel worktrees: provisions
        # its own pgdevkit-scoped Postgres database, builds the frontend once, and
        # serves it from the backend on a free port the OS picks itself (never kills
        # another worktree's dev server, never touches another workspace's data).
        # Prints the URL when ready. Override the port with --port <n> or BACKEND_PORT.
        agent-preview *args:
            uv run python scripts/agent_preview.py start {{args}}

        # Check whether a preview is already running for this workspace
        agent-preview-status:
            uv run python scripts/agent_preview.py status

        # Stop the preview running for this workspace, if any
        agent-preview-stop:
            uv run python scripts/agent_preview.py stop

        # Regenerate the typed API client: dump the OpenAPI schema, then run codegen
        generate-api:
            uv run python -m backend.dump_openapi
            cd frontend && bun run generate-api

        # Run backend tests (spins up/reuses the shared pgdevkit test container)
        test:
            uv run pytest
        """.replace("__BE_PORT__", str(be_port)).replace("__FE_PORT__", str(fe_port)),
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

        # Python / uv
        __pycache__/
        *.pyc
        .venv/
        *.egg-info/
        .python-version

        # pgdevkit — generated concatenation, never hand-edited or committed
        database/**/all.sql

        # skillup — companion skills materialized locally; only skills.lock.json is committed
        .claude/skills/
        .agents/skills/
        .agent/skills/

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

        Full-stack app: Vite + React + TanStack (Router/Query/Form/Table/Virtual) + Zustand on the frontend,
        FastAPI + pgdevkit (psycopg) on the backend, Postgres 17 in Docker.

        ## Dev

        Task running is via [`just`](https://github.com/casey/just) — run `just` to list all recipes.

        ```bash
        cp frontend/.env.example frontend/.env
        cp .env.example .env

        just install       # uv sync + bun install
        just db-up         # Postgres on :5432
        just generate-api  # dump OpenAPI schema + generate the typed client (once, and after backend model changes)
        just dev           # FastAPI (:{be_port}) + Vite (:{fe_port}) together

        # or run them separately:
        just backend     # FastAPI on :{be_port}
        just frontend    # Vite on :{fe_port} (run in a second terminal)
        ```

        ## Agent preview (multiple worktrees/agents at once)

        `just dev` hardcodes ports {be_port}/{fe_port}. If more than one worktree or
        agent might be running dev/screenshot work on this machine at the same time,
        use `just agent-preview` instead — it provisions its own pgdevkit-scoped
        Postgres database, builds the frontend once, and serves it from the backend
        on a free port the OS picks itself (never kills another process, never
        touches another workspace's data):

        ```bash
        just agent-preview            # prints the URL when ready, e.g. http://127.0.0.1:53214
        just agent-preview --rebuild  # force a fresh `bun run build` first
        just agent-preview-status     # check if one is already running for this workspace
        just agent-preview-stop       # stop it
        ```

        Pass `--port <n>` (or set `BACKEND_PORT`) to pin the port instead of letting
        the OS pick one.

        ## Tests

        ```bash
        just test
        ```

        Uses [pgdevkit](https://github.com/bmsuisse/pgdevkit)'s `ensure_testdb()` fixture
        (see `tests/conftest.py`) — starts the shared `pgdevkit-postgres` container if
        needed, creates a database scoped to this project+branch, and applies every
        `.sql` file under `database/` before tests run.

        ## Regenerate typed API client

        ```bash
        just generate-api
        ```

        Runs `backend/dump_openapi.py` (imports the FastAPI app directly, no running
        server needed) to write `frontend/openapi.json`, then `@hey-api/openapi-ts`
        generates `frontend/src/lib/generated/` — a typed SDK, TanStack Query options,
        and Zod runtime validators. Commit the generated output; it's the reviewable
        record of the frontend/backend contract, not a build artifact.

        ## Stack notes

        - No ORM. Postgres access via [pgdevkit](https://github.com/bmsuisse/pgdevkit)'s
          `pgdevkit.db` (psycopg) — see `backend/db.py`. Schema lives as `.sql` files
          under `database/`; see pgdevkit's `docs/database-layout.md` for the convention.
        - File-based routing: add files under `frontend/src/routes/`.
        - Client state: `useState` + Context first. Zustand only when crossing distant components.
        - URL state (filters, pagination): TanStack Router search params, not Zustand.
        """,
    )

    print(f"""
🎉 Project '{project}' is ready!

  cd {project}
  just install
  just db-up                        # start Postgres
  just generate-api                 # dump OpenAPI schema + generate the typed client
  just dev                          # FastAPI (:{be_port}) + Vite (:{fe_port}) together
""")


if __name__ == "__main__":
    main()
