---
name: dead-code-audit
description: >
  Find unused functions, classes, exports, files, stale or unused dependencies,
  outdated and vulnerable packages, and circular imports in Python and
  TypeScript/JS/Vue/React projects, using vulture, ruff, deptry, knip, madge
  and friends via ready-made scripts, then verify each finding before deleting
  anything. Use whenever the user wants to clean up a repo, remove dead code,
  find unused code or dependencies, check for outdated or stale libraries,
  shrink a codebase, or asks "what can we delete", "is this function used",
  "unused imports", "dependency audit", "tech debt cleanup" — even if they never
  say "dead code". Pairs with clean-code, improve-codebase-architecture and
  duplicatecode for the other cleanup signals.
---

# Dead Code Audit

Deleting unused code is the cheapest refactor there is, but static tools only
see static references. They flag false positives (FastAPI routes, Vue
components registered by name, plugin hooks, public library API, anything
reached by reflection) and miss nothing they cannot see. So the job has two
halves: **collect findings with the scripts, then verify each one** before
removing it. A wrong deletion costs far more than a missed one.

The scripts are read-only: they print findings and never modify or delete.

## 1. Run the audit

From the project root (the scripts use `uvx`, `bunx` or `npx`, so nothing is
installed permanently):

```sh
# Python (needs uv)
bash <skill-dir>/scripts/python_audit.sh [path] [min-confidence=80]

# TypeScript / JS / Vue / React
bash <skill-dir>/scripts/ts_audit.sh [path]
```

What each one runs, and what it tells you:

| Signal | Python | TypeScript / Vue |
|--------|--------|------------------|
| Unused functions, classes, variables | `vulture` (heuristic) | `knip` (files, exports, types) |
| Unused imports, locals, arguments | `ruff` (F401, F841, ARG) | `tsc` / `vue-tsc` `--noUnused*` |
| Unused, missing, transitive dependencies | `deptry` | `knip` |
| Circular imports, orphan modules | | `madge` |
| Outdated packages | `uv tree --outdated` | `bun`/`npm outdated` |
| Vulnerable packages | `pip-audit` | `osv-scanner` or `bun`/`npm audit` |

Not covered by a script: SQL (use Unity Catalog `system.access.table_lineage`
to find tables nobody reads, `sys.dm_db_index_usage_stats` on SQL Server) and
C# (Roslyn `IDE0051`/`IDE0052`/`CS8019`, `dotnet list package --outdated
--vulnerable`). Test-coverage gaps are a second dead-code signal: code no test
executes (`coverage run -m pytest && coverage report -m`).

For duplicated code, use `duplicatecode` (see `improve-codebase-architecture`).

## 2. Triage: verify before deleting

Work through findings highest-confidence first. For each candidate:

1. **Grep the whole repo** for the name, including strings, config, YAML,
   templates and docs. Dynamic use hides in `getattr`, `importlib`, route
   decorators, DI containers, `<component :is="...">`, serialized names.
   If [codegraph](https://github.com/colbymchenry/codegraph) is installed and
   indexed (`codegraph init`), `codegraph callers <symbol>` is a stronger check
   than grep: it follows callbacks and interface-to-implementation calls. Zero
   callers plus no string/config hits is good evidence; `codegraph impact <symbol>`
   shows what depends on it if you are unsure. It has no "list all unused"
   command, so use it per candidate, not as a scanner.
2. **Is it public API?** Exported from a package, documented, or used by other
   repos? Check `cross-repo-discovery` before removing anything shared.
3. **Is it an entry point?** CLI commands, FastAPI/route handlers, scheduled
   jobs, Databricks tasks, framework lifecycle hooks, `__all__` entries.
4. **Check history.** `git log -S<name>` shows why it exists; recently added
   code is often work in progress.
5. **Run the tests** after removal, and the type checker/build. With codegraph,
   `git diff --name-only | codegraph affected --stdin --quiet` lists just the
   test files that touch the change.

Classify each finding: `delete` (verified unused), `keep + whitelist`
(false positive, record it so it stops reappearing), or `unsure` (ask the
user; don't guess).

## 3. Silence false positives once

- vulture: put intentional names in `vulture_whitelist.py` (generate a
  starting point with `uvx vulture <path> --make-whitelist > vulture_whitelist.py`,
  then prune it by hand; the script picks the file up automatically).
- knip: `knip.json` (`entry`, `ignore`, `ignoreDependencies`) rather than
  inline ignores.
- ruff: targeted `# noqa: ARG001` with a reason only where the signature is
  forced by a framework.

## 4. Report and delete

Summarize as a short list per category: what was found, what was verified and
removed, what was kept and why, and what needs the user's decision. Delete in
small commits grouped by kind (unused imports, then dead functions, then
dependencies) and keep deletions separate from behaviour changes so a revert is
trivial. Dependency removals: run the full install and test suite afterwards,
since a transitive dependency can disappear with it.

Outdated and vulnerable packages are different from dead code: don't bulk
upgrade. Fix vulnerabilities first, upgrade patch/minor versions in one PR, and
treat major upgrades individually.

## Using codegraph safely

Use only the CLI queries (`init`, `callers`, `callees`, `impact`, `affected`);
they are local. Two things to know before enabling it for a user: `codegraph init`
creates a `.codegraph/` index directory in the repo (add it to `.gitignore`), and
anonymous usage telemetry is on by default (`export CODEGRAPH_TELEMETRY=0` or
`DO_NOT_TRACK=1`). Skip `codegraph install`, which edits agent configs and MCP
settings, unless the user asks for it.
