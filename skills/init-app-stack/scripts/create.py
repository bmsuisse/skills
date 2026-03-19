#!/usr/bin/env python3
"""
create.py — cross-platform project scaffolding (Mac / Linux / Windows)

Usage:
    uv run python create.py <project-name>

Creates:
    <project-name>/
        frontend/   Nuxt + Nuxt UI (bun)
        backend/    FastAPI (uv)
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
    print("\n📦 Frontend: Nuxt + Nuxt UI")

    run(
        ["bunx", "nuxi@latest", "init", "frontend", "--package-manager", "bun", "--no-install", "--no-git"],
        root,
        "nuxi init frontend",
    )
    run(["bun", "install"], fe, "bun install")
    run(["bun", "add", "@nuxt/ui", "tailwindcss"], fe, "bun add @nuxt/ui tailwindcss")

    write(
        fe / "nuxt.config.ts",
        """\
        export default defineNuxtConfig({
          modules: ['@nuxt/ui'],
          css: ['~/assets/css/main.css'],
          devtools: { enabled: true },
        })
        """,
    )

    write(
        fe / "assets" / "css" / "main.css",
        """\
        @import "tailwindcss";
        @import "@nuxt/ui";
        """,
    )

    write(
        fe / "app.vue",
        """\
        <template>
          <UApp>
            <NuxtPage />
          </UApp>
        </template>
        """,
    )

    print("✅ Frontend ready")

    # ── Backend ───────────────────────────────────────────────────────────────
    print("\n🐍 Backend: FastAPI + uv")

    be.mkdir(exist_ok=True)
    run(["uv", "init", "."], be, "uv init")
    run(["uv", "add", "fastapi[standard]"], be, "uv add fastapi[standard]")

    write(
        be / "main.py",
        """\
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI(title="Backend API", version="0.1.0")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


        @app.get("/health")
        async def health() -> dict:
            return {"status": "ok"}
        """,
    )

    # Append [tool.uv.scripts] to pyproject.toml if not present
    pyproject = be / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[tool.uv.scripts]" not in content:
            content += '\n[tool.uv.scripts]\ndev = "fastapi dev main.py"\n'
            pyproject.write_text(content, encoding="utf-8")

    print("✅ Backend ready")

    # ── Root .gitignore ───────────────────────────────────────────────────────
    write(
        root / ".gitignore",
        """\
        # Node / Bun
        node_modules/
        .nuxt/
        .output/
        dist/
        .bun/

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

    print(f"""
🎉 Project '{project}' is ready!

  Frontend:  cd {project}/frontend && bun run dev
  Backend:   cd {project}/backend  && uv run dev
""")


if __name__ == "__main__":
    main()
