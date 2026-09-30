---
name: bms-code-review
plugin: dev-workflow
description: >
  BMS code review that fans out one focused subagent per concern (architecture,
  duplication, security, correctness, agent-docs/skills, performance, and per-layer
  SQL/backend/frontend reviews) depending on what changed, with static checks
  (`bdt lint`) run first. Use instead of, or in addition to, the generic
  `/code-review` for any BMS repo diff or PR — "bms code review", "review my
  changes", step 5/8 of `dev-workflow`. Satisfies the PR-publish gate like
  `/code-review`.
---

# BMS code review

Reviews the current diff (or a PR number/branch given as argument) by
delegating to specialised subagents. You are the orchestrator: gather context,
spawn subagents **in parallel** (single message, multiple Agent calls), merge
and de-duplicate their findings, and report one ranked list.

Read [`references/ponytail.md`](references/ponytail.md) first and tell every subagent to read it too
(pass the file path). It is the yardstick for over-engineering findings.

## 0. Prepare

1. Determine the diff: `git diff $(git merge-base HEAD origin/main)...HEAD`
   (or `gh pr diff <n>`). List changed files and classify them:
   - **SQL/DB**: `*.sql`, migrations, `*.test_data.json`, files calling `.execute(`
   - **Backend**: `*.py` outside tests
   - **Frontend**: `*.ts`, `*.tsx`, `*.vue`, `*.css` and `package.json`
   - **Docs/agent config**: `AGENTS.md`, `CLAUDE.md`, `.claude/`, `skills/`, `README`, `docs/`
2. Run static checks first; they are cheap and deterministic:
   `bdt lint <changed paths>` (Postgres/psycopg SQL rules, pydantic-model
   placement, tooling config) and `bdt find-injection --diff` (SQL built from
   f-strings/concatenation, eval/exec/shell/unsafe deserialisation, innerHTML/
   `dangerouslySetInnerHTML`/un-sandboxed iframes, missing or weakened CSP).
   Its errors are definite findings; its "review" items go to the Security
   subagent to verify. Also run the repo's own `ruff`/`ty`/`biome`
   if configured. Report their findings verbatim and don't have subagents
   re-derive them.
3. Give each subagent: the diff, the changed-file list, the relevant
   skill names below, and the output format at the bottom.

## 1. Architecture gate (run first, alone)

One subagent answers: is the work placed in the right layer?

- Do in **SQL** whatever is declarative (filtering, joins, aggregation,
  ranking, constraints, defaults, generated columns).
- Do in **backend** (Python) the business logic that isn't cleanly declarative.
- Do in **frontend** only what must be there (presentation, interaction, local UI state).

If it finds a **big issue** (wrong layering, logic duplicated across layers,
data model that fights the feature): **stop**. Report only that and tell the
user the change must be redone; don't spend effort on line-level review.
Otherwise continue.

## 2. Parallel reviews

Spawn only the ones the diff calls for.

| Subagent | When | Skills / tools to load | Looks for |
|---|---|---|---|
| **Duplication** | any code change | [bmsuisse/duplicatecode](https://github.com/bmsuisse/duplicatecode) (run its CLI on the changed paths) | Copy-pasted or near-identical logic, re-implemented helpers that already exist in the repo or in bmsuisse packages (`cross-repo-discovery`) |
| **Security** | any code change | `bdt find-injection --diff` output (devtools#54), `fastapi-azure-auth` | Verify each "review" item `find-injection` listed (real risk or false positive?), plus what a static tool can't see: missing input validation, secrets. **If auth-related code or routes changed** (or new endpoints were added): verify every route is authenticated and authorised |
| **Correctness** | any code change | `coding-guidelines-*` for the language | Does the implementation do what the issue/PR says? Edge cases: empty/None/duplicates, timezones, off-by-one, concurrency, transactions, error paths, pagination, idempotency |
| **Agent docs & skills** | always | — | Were `AGENTS.md`/`CLAUDE.md` and friends followed? Do they need updating because of this change? Point out relevant skills from `bmsuisse/skills` (e.g. `pgdevkit` for Postgres/test data, `testing-strategy`, `fastapi-guideline`, `tanstack-best-practices`) — pick by changed files |
| **Performance** | SQL/DB or backend data access changed | `sql-optimization`, `coding-guidelines-sql` | Work that should be one SQL statement but is a Python loop / N+1; missing indexes; unbounded results. **Are table sizes known?** If not, query them via the database MCP or ask the user before signing off — never guess |
| **SQL/Database** | SQL/DB files changed | `coding-guidelines-sql`, `sql-optimization`, `pgdevkit` | Naming, constraints, migration safety (locks, backfills, reversibility), test-data sidecars |
| **Backend** | Python changed | `coding-guidelines-python`, `fastapi-guideline`, `testing-strategy` | Style, typing, layering, error handling, tests exist (HTTP-level first) |
| **Frontend** | frontend changed | `coding-guidelines-typescript`, `tanstack-best-practices`, `bms-frontend-design`, `kendo-ui-*`/`rich-data-tables` where used | Framework idioms; **uses bmsuisse packages where appropriate** instead of hand-rolled equivalents (check `package.json` and `cross-repo-discovery`); accessibility; states (loading/empty/error) |

For a **large** frontend change (many files or new screens), give the Frontend
subagent its own sub-fan-out: one for data fetching/state (TanStack), one for
components/design, and run `/design-review` if screenshots exist.

## 3. Report

Merge findings, drop duplicates and anything `bdt lint` already reported,
and rank by severity. Verify each finding against the code before reporting;
drop speculation. Group as **Blocking / Should fix / Nit**, each with
`file:line`, the problem, and a concrete fix. End with which subagents ran
and which were skipped (and why).

### Subagent output format

Return findings only, as `severity | file:line | problem | suggested fix`,
plus a one-line "nothing found" if clean. No praise, no restating the diff.

## Options

- `--comment`: post the merged findings as PR comments (`bdt pr comment --file`).
- `--fix`: apply the Blocking and Should-fix findings afterwards; ask if unsure.
