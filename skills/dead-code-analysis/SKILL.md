---
name: dead-code-analysis
plugin: maintenance
description: >
  Find and remove dead code in a Python and/or React/TypeScript repo: unused
  code, unreferenced .sql files, backend routes no frontend calls, unused
  exports, files and dependencies. Uses `bdt dead-code`, ruff, vulture, deptry,
  knip. Use for "find dead code", "remove unused code", "what can we delete",
  "clean up unused routes/exports/deps". Not for upgrades (bump-dependencies)
  or vulnerabilities (audit-dependencies).
---

# Dead code analysis

Tools only *suggest* candidates. Verify each one before deleting.

## 1. Run

From the repo root, with the repo's own interpreter:

| Scope | Command |
|---|---|
| SQL files + routes | `uv run bdt dead-code` |
| Python unused imports/vars/args | `uv run ruff check --select F401,F841,F811,ARG --no-fix .` |
| Python unused functions/classes | `uvx vulture . --min-confidence 80` |
| Python unused deps | `uv run deptry .` |
| TS/React files, exports, deps | `bun x knip` |
| TS unused imports/vars | `bun x @biomejs/biome lint .` |

- `bdt dead-code` runs only what is configured in `[tool.bdt.dead_code]` (`sql_roots`, `[[tool.bdt.dead_code.apps]]`),
  exit 2 if nothing is. Configure it, don't skip it: [README](https://github.com/bmsuisse/devtools#bdt-dead-code).
  Update bdt first (`uv tool upgrade bmsdna-devtools`).
- Big repo adopting `routes`: `uv run bdt dead-code --update-baseline`, commit the baseline, don't mass-delete.
- vulture is noisy: keep `--min-confidence 80`; whitelist framework-reached names in `vulture_whitelist.py`.
- knip reporting half the repo means entry points are missing: add a `knip.json` first. `--production` ignores test-only usage.

## 2. Triage

Before deleting, check for:

1. Dynamic use: `getattr`, string imports, entry points, decorator registration, templates, `import.meta.glob`, lazy `import()`.
2. Public surface: shared package, other repos (`/cross-repo-discovery`), external API, webhooks, health checks.
3. Test-only callers: dead too, delete both.
4. Use via DB/config: procedure names, feature flags, string-built names.

Result: **delete**, **keep + exclude** (add to tool config/whitelist), or **ask** (list for a human).

## 3. Remove

- One logical removal per commit (e.g. route + its SQL + tests + regenerated client).
- Then `uv remove` / `bun remove` the dependency nothing imports, in its own commit.
- Delete, don't comment out. No unrelated refactors.
- Re-run the tool and the relevant tests/type check (`uv run ty check`, `bun run tsc --noEmit`).

## 4. Report

PR lists what was removed, what was kept as false positive (and where excluded), and what needs a human decision.
