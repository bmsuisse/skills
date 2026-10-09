---
name: bms-code-review
plugin: dev-workflow
description: >
  BMS code review that fans out one focused subagent per concern (architecture,
  duplication, security, correctness, agent-docs/skills, performance, and per-layer
  SQL/backend/frontend reviews) depending on what changed. Use instead of, or in addition to, the generic
  `/code-review` for any BMS repo diff or PR — "bms code review", "review my
  changes", step 5/8 of `dev-workflow`. Satisfies the PR-publish gate like
  `/code-review`.
---

# BMS code review

Reviews the current diff (or a PR number/branch given as argument) by
delegating to specialised subagents. You are the orchestrator: gather context,
spawn subagents **in parallel** (single message, multiple Agent calls), merge
and de-duplicate their findings, and report one ranked list.

Read [`references/ponytail.md`](references/ponytail.md) first. It is the yardstick for
over-engineering findings. Pass its path only to the Correctness, Backend and
Frontend subagents; give the others this two-line summary instead: *"Flag code
that skips a rung: reinvented helper, new dependency for a few lines,
single-implementation abstraction, speculative config. Never flag validation,
security or accessibility for removal."*

## Subagent types (model and reasoning effort)

Spawn each role with the matching agent type so it runs on Sonnet at the right
reasoning effort. Installed via the `dev-workflow` plugin the types are
namespaced (`dev-workflow:bms-review-core` etc.); as project agents they are
plain `bms-review-core`. Use whichever appears in your agent list. Haiku is not good enough for any role (it misses the
blocking bugs and states false facts); don't use it.

| Agent type | Effort | Roles |
|---|---|---|
| `bms-review-core` | high | Correctness, Security, **all verifiers** |
| `bms-review-standard` | medium | Architecture gate, SQL/Database, Backend, Frontend, Performance |
| `bms-review-light` | low | Agent docs & skills, Duplication |

If these agent types are not installed (they ship with the `dev-workflow`
plugin), fall back to `general-purpose` with `model: "sonnet"`. Merging and
report writing (you) stay at your own effort.

## Effort

- `--quick` (what `dev-workflow` step 5 uses; also the default for diffs under ~5 files that touch no SQL/auth): one
  single-pass review by you, no fan-out, skip test files, at most 4 findings.
- full (default otherwise, or `--full`): everything below. Roughly 10x the
  token cost of `--quick`, so use it for SQL/auth/large changes and the
  second review round.

## 0. Prepare

1. Determine the diff: `git diff $(git merge-base HEAD origin/main)...HEAD`
   (or `gh pr diff <n>`). If empty, also try `git diff HEAD`; if that is empty
   too, the branch may already be merged: review the merge commit's parents
   (`git diff <merge>^1 <merge>^2`) or say so and stop — never invent findings. Save the diff to a file and
   give every subagent its path, a 2–3 line description of the feature, and
   issue-specific "look specifically for" bullets. List changed files and classify them:
   - **SQL/DB**: `*.sql`, migrations, `*.test_data.json`, files calling `.execute(`
   - **Backend**: `*.py` outside tests
   - **Frontend**: `*.ts`, `*.tsx`, `*.vue`, `*.css` and `package.json`
   - **Docs/agent config**: `AGENTS.md`, `.claude/`, `skills/`, `README`, `docs/`
2. Don't run or re-derive linters and static checks: prek enforces them.
   Spend the review on what they can't see.
3. Give each subagent: the diff, the changed-file list, the relevant
   skill names below, and the output format at the bottom.

## 1. Architecture gate (run first, alone)

One subagent answers: is the work placed in the right layer?

- Do in **SQL** whatever is declarative (filtering, joins, aggregation,
  ranking, constraints, defaults, generated columns).
- Do in **backend** (Python) the business logic that isn't cleanly declarative.
- Do in **frontend** only what must be there (presentation, interaction, local UI state).

Also check **altitude**: special cases layered onto shared infrastructure
(e.g. `if prospect … else customer …` sprawl) — name the more general change.

**Stop only for a redo-level problem:** the change is in the wrong layer as a
whole, business logic is duplicated across layers, or the data model fights
the feature, so most line-level findings would be void once it is redone.
Report just that and tell the user the change must be redone.

Anything fixable in place (a bug, a missing constraint or lock, business logic
that belongs in one SQL statement, missing auth) is **not** a stop: put the
gate finding at the top of the report and continue with the parallel reviews.
When unsure, continue.

## 2. Parallel reviews

Spawn only the ones the diff calls for.

| Subagent | When | Skills / tools to load | Looks for |
|---|---|---|---|
| **Duplication** | any code change | [bmsuisse/duplicatecode](https://github.com/bmsuisse/duplicatecode) (see recipe below) | Copy-pasted or near-identical logic, re-implemented helpers that already exist in the repo or in bmsuisse packages (`cross-repo-discovery`) |
| **Security** | any code change | `fastapi-azure-auth` | Injection paths a linter can't judge (SQL/command/HTML built from data that crosses a trust boundary, unsafe deserialisation, un-sandboxed iframes, weak CSP), missing input validation, secrets. **If auth-related code or routes changed** (or new endpoints were added): verify every route is authenticated and authorised |
| **Correctness** | any code change | `coding-guidelines-*` for the language | Does the implementation do what the issue/PR says? Read the whole enclosing function (bugs in untouched lines of a touched function are in scope). Hunk checklist: inverted conditions, off-by-one, falsy-zero, missing `await`, swallowed `except`, copy-paste wrong variable, mutual exclusion of optional FKs. **Removed-behavior audit:** for every deleted/replaced guard, validation or test, name the invariant and where it is re-established. **Cross-file trace:** grep callers of each changed function; check new preconditions and return shapes. **Concurrency:** check-then-act races, lock order (deadlocks), idempotency under concurrent retry, uniqueness enforced by a constraint rather than a read. **Numerics:** money as `Decimal`/numeric never float, NaN/Infinity, precision, ties in ORDER BY (add a unique tiebreaker for OFFSET paging). **Sibling-guard sweep:** when the diff adds a member to a mutually-exclusive or enumerated set (prospect vs customer, a new status/role), grep every site that tests the old members and record whether each was updated; also review any "fix: found in review" commit itself. **Fix location:** if a diff patches several callers of one shared function, name the single fix inside that function. **Side-effect ordering:** an irreversible external write (ERP/Graph/email/payment) followed by a fallible call leaves orphans or duplicates on retry. **Input-class sweep** for new parsers, guards and fallbacks: one probe each for empty, quoted, case, comments/literals, CTE/alias names, unparseable input; report the classes tried. Where cheap, reproduce with a tiny script or `pytest -k` before reporting |
| **Agent docs & skills** | always | — | Grep the whole repo (docs site, README, code comments) for claims like "not supported"/"silently disables" about behaviour the diff changes. Were `AGENTS.md` and friends followed? Do they need updating because of this change? Point out relevant skills from `bmsuisse/skills` (e.g. `pgdevkit` for Postgres/test data, `testing-strategy`, `fastapi-guideline`, `tanstack-best-practices`) — pick by changed files |
| **Performance** | SQL/DB or backend data access changed | `sql-optimization`, `coding-guidelines-sql` | Work that should be one SQL statement but is a Python loop / N+1; missing indexes; unbounded results. **Get real sizes, don't guess:** run `pgdb get-stats <database dir> <schema.table> …` (latest `pgdevkit`; reads the committed `database/_stats/` JSON, no DB access; `--no-columns` for table-level row counts only) for every table the diff queries or migrates, and use row counts and column stats (`n_distinct`, `null_fraction`; `row_count` is a planner estimate, null if never analyzed) to judge scans, missing indexes and migration locks. If `get-stats` is missing, upgrade pgdevkit; if the repo has no `_stats/`, ask the user (or run `pgdb update-stats` against a real DB) rather than assuming |
| **SQL/Database** | SQL/DB files changed | `coding-guidelines-sql`, `sql-optimization`, `pgdevkit` | Naming, constraints, migration safety (locks, backfills, reversibility), test-data sidecars |
| **Backend** | Python changed | `coding-guidelines-python`, `fastapi-guideline`, `testing-strategy` | Style, typing, layering, tests exist (HTTP-level first). **Error handling:** flag every `try/except` that swallows an error (bare/broad `except`, `pass`, returning a default): it must re-raise, or log (with traceback) and carry a one-line justification of why continuing is safe. Let errors propagate to the framework's handler otherwise |
| **Frontend** | frontend changed | `coding-guidelines-typescript`, `tanstack-best-practices`, `bms-frontend-design`, `kendo-ui-*`/`rich-data-tables` where used | Framework idioms; **uses bmsuisse packages where appropriate** instead of hand-rolled equivalents (check `package.json` and `cross-repo-discovery`); accessibility; states (loading/empty/error). **Every HTTP request** (query or mutation) needs a loading indicator and visible error handling: prefer `@bmsuisse/ui` `AsyncBoundary` (or `LoadingState`/`ErrorState`/`InlineError`) for queries, `isPending` on submit buttons plus an error toast/`InlineError` for mutations; flag unhandled `.catch`-less `fetch`/`await` calls and ignored `isError`. If bmsui lacks what's needed, say so (upgrade `@bmsuisse/ui` first, else file an issue there) |

**Duplication recipe.** Need duplicatecode >= 0.3.2 (`duplicatecode -V`; else `uv tool upgrade duplicatecode`, or `uvx duplicatecode`). Add `--embed` to every command below when local ollama has embeddinggemma (`curl -s -m 3 127.0.0.1:11434/api/tags | grep -q embeddinggemma`): the best preset in the repo's benchmark, it finds re-implementations that share no tokens. Without it, run static. Never use `--embed=openai|cohere`: they upload the code.

1. **New code vs existing:** `git diff <base> | duplicatecode diff --repo . [--embed]`. This is the main check: does the added code re-implement something that already exists?
2. **Copies inside the changed files:** `duplicatecode review <changed paths> [--embed]` (ranked groups, tiers IDENTICAL / NEAR-COPY / SIMILAR, what differs). Read the code before reporting a SIMILAR group.
3. **Pasted blocks:** `duplicatecode fragments <changed paths>` finds 4+ identical statements shared by different functions.
4. **Does a helper exist for X?** `duplicatecode find "<what the new code does>" <repo root> --embed` (needs embeddings).

Report a group only if the duplicated code is in the diff or the diff adds a new copy. Tell the fixer what to parameterize (`review` prints what differs).

For a **large** frontend change (many files or new screens), give the Frontend
subagent its own sub-fan-out: one for data fetching/state (TanStack), one for
components.

## 3. Verify and report

1. Merge findings and drop duplicates.
2. **Verify pass:** verify only Blocking and Should-fix candidates (nits skip
   it). Spawn one verifier per file's candidates, up to 4 findings each (in parallel).
   Each re-reads the code, quotes the offending line, and returns
   `CONFIRMED`, `PLAUSIBLE` or `REFUTED`. Keep the first two; drop REFUTED and
   count them. Subagents pass borderline candidates up instead of dropping them.
3. **Rank and cap** at about 8 findings, correctness/security/data-loss first.
   Group as **Blocking / Should fix / Nit**. *Blocking* is reserved for
   verified bugs, security issues and data loss/corruption. Perf concerns and
   missing work outside the task's stated scope are at most *Should fix*
   unless demonstrated (e.g. by table sizes or a reproduction). Findings that
   would exceed the cap go into a one-line "also noticed" list.
4. Each finding: `file:line`, the problem, a concrete `failure_scenario`
   (input/state → wrong result), and a fix. When citing a convention, quote
   the exact rule and its source file. Don't assert facts about the repo
   (frameworks, versions) you didn't check.
5. End with which subagents ran, which were skipped (and why), whether you
   had to play all roles yourself because no Agent tool was available, and the
   number of refuted candidates.

### Subagent output format

Return findings only, as `severity | file:line | problem | failure_scenario | suggested fix`,
plus a one-line "nothing found" if clean. A finding without a concrete
failure_scenario is dropped. No praise, no restating the diff.

## Options

- `--comment`: post the merged findings as PR comments (`bdt pr comment --file`).
- `--fix`: apply the Blocking and Should-fix findings afterwards; ask if unsure.
