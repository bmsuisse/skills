---
name: bms-plan-review
plugin: dev-workflow
description: >
  Review an implementation plan before any code is written: checks it against
  BMS conventions and the existing skills (layering, SQL-first, testing,
  auth, frontend packages) and flags gaps. Use for step 3 of `dev-workflow`
  (implementation plan) — "review the plan", "is this plan right", "check my
  implementation plan" — before uploading the plan to the PR.
---

# BMS plan review

Review a written implementation plan (a file, PR comment, or the plan in the
conversation) **before implementation starts**. Cheaper to fix here than in code review.

Load the `ponytail` skill first.

## Steps

1. Read the plan, the linked issue/PR (all comments), and the repo's
   `AGENTS.md`/`CLAUDE.md`. Check the code the plan touches (use CodeGraph
   if `.codegraph/` exists).
2. Check the plan against the relevant existing skills; load those that match
   the plan's scope and say which you used:
   - Layering: SQL for declarative work, Python for business logic, frontend
     only where needed (same rule as `bms-code-review` step 1). Order should be Database → Backend → Frontend.
   - Database: `coding-guidelines-sql`, `sql-optimization`, `pgdevkit`. Are
     table sizes known? Migration safety?
   - Backend: `coding-guidelines-python`, `fastapi-guideline`, `fastapi-azure-auth` (auth for every new endpoint).
   - Frontend: `coding-guidelines-typescript`, `tanstack-best-practices`,
     `bms-frontend-design`; bmsuisse packages used where they exist (`cross-repo-discovery`).
   - Tests: `testing-strategy` — HTTP-level first, then Playwright e2e for user flows.
3. Look for: missing requirements from the issue, wrong or missing layers,
   reinventing something that already exists (in the repo or bmsuisse
   packages), unhandled edge cases, security/auth gaps, perf risks, missing
   tests, unclear step ordering, and over-engineering (scope beyond the issue).
4. Report: **Verdict** (go / go with changes / redo), then findings ranked
   Blocking / Should fix / Nit, each with the plan section it refers to and
   a concrete change. Ask the user about genuine open questions instead of guessing.

Don't rewrite the plan yourself unless asked; give the edits.
