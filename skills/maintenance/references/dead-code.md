# maintenance: dead-code

Tools only *suggest*. Verify each candidate before deleting.

| Scope | Command (repo root) |
|---|---|
| SQL files + routes | `uv run bdt dead-code` |
| Python unused imports/vars/args | `uv run ruff check --select F401,F841,F811,ARG --no-fix .` |
| Python unused functions/classes | `uvx vulture . --min-confidence 80` |
| Python unused deps | `uv run deptry .` |
| TS/React files, exports, deps | `bun x knip` |
| TS unused imports/vars | `bun x @biomejs/biome lint .` |

- `bdt dead-code` runs only what `[tool.bdt.dead_code]` configures (`sql_roots`, `[[tool.bdt.dead_code.apps]]`), exit 2 if
  nothing. Configure it, don't skip it: [README](https://github.com/bmsuisse/devtools#bdt-dead-code). Update bdt first
  (`uv tool upgrade bmsdna-devtools`). Adopting `routes` on a big repo: `--update-baseline`, commit it, don't mass-delete.
- vulture is noisy: whitelist framework-reached names in `vulture_whitelist.py`. knip reporting half the repo
  means entry points are missing: add `knip.json`. `--production` ignores test-only usage.

Before deleting, check for: dynamic use (`getattr`, string imports, entry points, decorator registration, templates,
`import.meta.glob`, lazy `import()`); public surface (shared package, other repos via `/cross-repo-discovery`, external
API, webhooks, health checks); use via DB/config (procedure names, flags). Test-only callers are dead too.
Result per candidate: **delete**, **keep + exclude** (add to tool config), or **ask**.

Remove one logical unit per commit (route + its SQL + tests + regenerated client), then `uv remove`/`bun remove`
unused dependencies separately. Delete, don't comment out. Re-run the tool, type check and relevant tests.
