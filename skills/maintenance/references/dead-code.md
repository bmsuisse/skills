# maintenance: dead-code

Tools only *suggest*. Verify each candidate before deleting.

**Run per project directory**, not at the repo root: every dir with a `pyproject.toml` / `bun.lock`
(`find . \( -name pyproject.toml -o -name bun.lock \) -not -path '*/node_modules/*' -not -path './.*'`). knip and biome
fail or lie at a root without `package.json` (monorepos have `frontend/` or one per app, run `bun install --frozen-lockfile` first; a root `package.json` without lockfile is a stray).
A virtual uv workspace root can't run deptry: run it per member.

| Scope | Command |
|---|---|
| SQL files + routes | `uv run bdt dead-code` (repo root) |
| Python unused imports/vars | `uvx ruff check --select F401,F841,F811 --no-fix .` (skip if `F` is already selected) |
| Python unused functions/classes | `uvx --python <requires-python> vulture . --exclude .venv,node_modules,tests --ignore-decorators "@*.get,@*.post,@*.put,@*.patch,@*.delete,@*.websocket,@pytest.fixture" --min-confidence 80` |
| Python unused deps | `uv run --with deptry deptry . --ignore DEP001,DEP003,DEP004` (those are import problems, not dead code) |
| TS/React files, exports, deps | `bun x knip` |
| TS unused imports/vars | `bun x @biomejs/biome lint src --only=correctness/noUnusedImports --only=correctness/noUnusedVariables` |

## bdt dead-code

Runs only what `[tool.bdt.dead_code]` configures, exit 2 if nothing ([README](https://github.com/bmsuisse/devtools#bdt-dead-code)).
Needs bdt >= 0.31.0 *in the project*: `uv run bdt --version`; if older `uv lock --upgrade-package bmsdna-devtools`
and raise the specifier to `>=0.31.0` (or `uv add --group dev bmsdna-devtools` if absent). Minimal config:

```toml
[tool.bdt.dead_code]
sql_roots = ["backend/db/queries"]            # folders of *loaded* queries, not migrations
[[tool.bdt.dead_code.apps]]
name = "app"
app = "backend.main:app"                      # module:attr, imported with app_dir as cwd
app_dir = "backend"                           # if the module isn't importable from the root
frontends = ["frontend/src"]                  # this app's own frontends only
exclude_prefixes = ["/external_api"]
exclude_paths = ["/callback", "/logout", "/api/me", "GET /health"]   # auth/health/service routes
```

`routes` imports the app: `uv sync` first; if import fails on required settings (e.g. `MS_CLIENT_SECRET must be set`)
set `env = { IS_TEST = "1" }` or point `openapi = "<committed openapi.json>"` at a schema instead. First run usually flags health, SPA
catch-all, `/auth/*`, `/test/*`: add them to `exclude_paths`. Big repo adopting it:
`--update-baseline`, commit, don't mass-delete.

## Tool noise

- **vulture** skips files it can't parse (t-strings, `except A, B:` need Python 3.14): use the project's Python and
  check the output for `invalid syntax`. Start at `--min-confidence 80` (still hundreds of lines on a big repo): go package by package, don't triage the whole list. Route handlers and pydantic fields dominate the output: leave handlers to
  `bdt dead-code`, ignore model fields, whitelist the rest (`--make-whitelist`). Decorator-registered functions
  (`@x.register`) are false positives.
- **knip** floods on generated code: add `knip.json` with `{"ignore": ["src/lib/generated/**"], "ignoreBinaries": ["uv"]}`
  (adapt), then entry points if still noisy. Types only used in `.d.ts` are false positives.
  `--production` ignores test-only usage.
- **deptry** is noisy in scripts and non-first-party packages: scope with `--exclude`/`--known-first-party`, focus on
  DEP002 (unused). Implicit runtime dependencies are false positives (`python-multipart`, `itsdangerous`, `tzdata`,
  `fastexcel`, `websockets`): ask before removing. A dependency imported only by another workspace member (`lib/`)
  belongs in that member's pyproject.

## Triage and remove

Before deleting, check for: dynamic use (`getattr`, string imports, entry points, decorator registration, templates,
`import.meta.glob`, lazy `import()`); public surface (shared package, other repos via `/cross-repo-discovery`, external
API, webhooks, health/auth routes); use via DB/config (procedure names, flags, a doc referencing a `.sql`).
Test-only callers are dead too. Per candidate: **delete**, **keep + exclude** (tool config), or **ask**.

Remove one logical unit per commit (route + its SQL + tests + regenerated client), then `uv remove` (`--group <g>`
for dev/group deps) / `bun remove` unused dependencies separately. Delete, don't comment out. Re-run the tool, type
check and relevant tests.
