---
name: branching-strategy
plugin: dev-workflow
description: >
  The BMS git branching and CI test-placement model: `dev` is the branch all work is based on, promoted
  `dev` -> `test` -> `main`; build policies on all three; unit and E2E tests split by area and selected per PR
  via `bdt` required labels; a nightly build that runs everything on `dev` and deploys it to `test`; promotion
  PRs between dev/test/main skip tests; PRs to `main` are fixes only. Use whenever setting up a new repo's
  branches, pipelines or branch policies, adjusting or auditing an existing project to this model, deciding
  which branch a PR should target or where a test should run, or when the user mentions "branching strategy",
  "build policy", "which tests run on a PR", "test labels", "e2e labels", "nightly build", "hotfix",
  "promote to test/main" or `[tool.bdt.pr.required_labels]` — even if they don't say "branching".
---

# Branching strategy

Three long-lived branches, one direction of flow:

```
feature/fix branch ──PR──▶ dev ──PR──▶ test ──PR──▶ main
                           (tests)    (no tests)   (no tests)
                             │
            nightly: full tests on dev, then deploy dev to the test environment
```

The point of the model: **every line of code is tested at the cheapest place to catch it, and promotion is
then a pure merge.** Tests run where code *enters* the flow (PRs into `dev`) and on a schedule (nightly);
promotion PRs only move code that has already been tested, so rerunning tests there costs time and adds
nothing.

Use this skill to **set up** a project that doesn't follow the model yet, or to **audit/adjust** one that
partly does. Start by reading the repo's current state (branches, pipeline YAML, `[tool.bdt.pr]` in
`pyproject.toml`, existing branch policies — see `references/azure-devops-policies.md`) and list the gaps
against the rules below before changing anything.

## The rules

1. **`dev` is the base for all work.** Branch and worktree off `dev` (`bdt worktree <name>` already defaults
   to it), PR into `dev`. Make `dev` the repository's default branch so tools and humans target it without
   thinking. `test` and `main` only ever receive promotions (plus fixes to `main`, rule 7).
2. **`dev`, `test` and `main` all carry a build policy.** Required, blocking, no direct pushes. It matters
   on `test` and `main` even though tests are skipped there: it forces every change through a PR, it still
   runs the build/lint/type-check part of the pipeline, and it gives one place that says "this was verified"
   before a deploy. A branch without the policy is a branch anyone can push untested code into.
3. **Tests are split by product area, and the PR itself decides which areas run, through labels.** Both
   unit and E2E tests live in per-area folders (`tests/unit/<area>/`, `tests/e2e/<area>/`). Each area has a
   label `test-<area>`, plus `test-full` for broad/cross-cutting changes. The author labels the PR with every
   area the change touches; CI runs only those folders, in both tiers. Enforce it with `bdt` required labels
   (below) so a PR can't even be created without that decision. Lint, type-check and the build are cheap and
   area-agnostic: they run in full on every PR.
4. **Promotion PRs run no tests.** Any PR whose source *and* target are both in {`dev`, `test`, `main`}
   skips the test stages: the code was tested when it entered `dev` and again in the nightly run. The build
   policy still applies; the pipeline just marks the test stages skipped.
5. **A nightly build on `dev` runs the complete suite** (every area, unit and E2E) and, only if green,
   deploys `dev` to the `test` environment. It is the safety net for the per-area shortcut in rule 3: a
   change labeled `test-visits` that quietly broke `customers` is caught here, not in production. Run it
   even when `dev` hasn't changed (`always: true`), because drift in data, dependencies and the environment
   breaks tests too.
6. **Promotion order is `dev` -> `test` -> `main`.** No skipping `test`. Opening the `dev` -> `test` PR is
   what a human does when `test` is needed sooner than the nightly, or to mark a release candidate.
7. **PRs into `main` are only allowed for fixes.** Two shapes qualify: the promotion `test` -> `main`, and a
   fix branch (`fix/...` or `hotfix/...`) for something broken in production. A fix branch is *not* covered
   by rule 4 — its code hasn't been tested anywhere yet — so it runs tests like any other PR, with labels.
   After it merges, merge `main` back into `dev` (a `main` -> `dev` promotion PR, no tests) so the fix
   isn't lost or reverted by the next promotion. Features, refactors and chores never target `main`.

### What runs where

| PR / build | Lint, types, build | Unit + E2E | Build policy |
|---|---|---|---|
| feature -> `dev` | all | areas from labels | yes |
| fix -> `main` | all | areas from labels | yes |
| `dev` -> `test`, `test` -> `main`, `main` -> `dev` (both ends in dev/test/main) | all | skipped | yes |
| push to `test` / `main` (after merge) | build | skipped | deploys to its environment |
| nightly on `dev` | all | **all areas** | then deploys `dev` to `test` env |

A PR from a feature branch into `test` is a mistake, not a variant: it would put untested code on `test`.
Reject it in the same guard as rule 7 (see `references/pipeline.md`).

## Splitting tests by area

- An *area* is a product feature area (`customers`, `orders`, `route_planning`), the same vocabulary in both
  tiers. Use the same folder name in `tests/unit/` and `tests/e2e/`; an area that exists in only one tier is
  fine (that tier is simply skipped for it).
- Keep a `shared` area for specs that belong to no single feature (responsive/UI audits, cross-cutting
  helpers' own tests) and let `shared` code changes use `test-full`.
- Move tests into the area that owns the *behaviour*, not the file that happens to be imported. A unit test
  of a pricing function belongs to `orders` if orders is what breaks when pricing breaks.
- Don't hand-split a flat test suite in one go. Start with the largest or slowest folder, keep the rest in
  `shared`, and move tests as they are touched; the nightly run covers the transition.
- Shared code (auth, layout, API client, DB schema, config, dependencies) is not owned by any area, so
  changing it means `test-full`. Say that in the repo's contributor notes.

## Required labels with `bdt`

`bdt pr create` can require at least one label per group before it creates the PR, configured in
`pyproject.toml`:

```toml
[tool.bdt.pr.required_labels]
# One group; the PR needs >= 1 label from it. Keep in sync with the folders under tests/unit/ and
# tests/e2e/ (the pipeline derives the areas from the folders, so this list is the only place to edit).
test_area = ["test-customers", "test-orders", "test-shared", "test-full"]

# Optional: auto-add the label from the commit scope, so `feat(orders): ...` -> test-orders
[tool.bdt.pr.scope_labels]
orders = "test-orders"
```

- Area folder `snake_case` -> label `kebab-case` (`route_planning` -> `test-route-planning`).
- The check is global, not per target branch, so promotion PRs need a label too. Give promotion recipes a
  default of `test-full` (e.g. `bdt pr create --target test --label test-full`); the pipeline ignores the
  label there, it exists only to satisfy `bdt`. Put the three flows in the repo's task runner
  (`pr-dev`, `pr-test`, `pr-main`) so nobody types branch names, plus a recipe that lists the area labels.
- Labels are the author's declaration, so judge them honestly: label every area the diff touches, and use
  `test-full` for shared code. When unsure, go broader — a slow PR costs minutes, a missed regression is
  paid for in production.
- A new area is two edits: the `tests/{unit,e2e}/<area>/` folder and its label in `required_labels`.
- Enforce twice: `bdt` blocks creation locally, and the pipeline fails a PR build that has no area label
  (a PR opened in the portal, or a label removed later, skips `bdt`). If the pipeline can't read the labels
  (API error), it falls back to the full suite rather than silently running nothing.
- A repo that already uses other label names (e.g. `e2e-<area>`) can keep them; the prefix is a choice, but
  one label must select the area's unit *and* E2E tests, otherwise authors have to remember two.

## Setting a project up — checklist

1. Branches: create `dev` and `test` from `main` if missing; set `dev` as the default branch.
2. Test layout: split unit and E2E tests into `tests/unit/<area>/` and `tests/e2e/<area>/`. Add
   `required_labels` (and optionally `scope_labels`) to `pyproject.toml`.
3. Pipeline (`references/pipeline.md`): `executeTests` rule for promotion PRs, a `Plan` stage that turns PR
   labels into the area list, unit and E2E stages that run only those areas, a nightly schedule on `dev`
   that runs everything and deploys to `test` when green, deploy-only runs for pushes to `test`/`main`, and
   the guard for rule 7.
4. Policies (`references/azure-devops-policies.md`): build validation on `dev`, `test`, `main` pointing at that
   pipeline; reviewer minimums; no bypass.
5. Task-runner recipes `pr-dev` / `pr-test` / `pr-main` with the default labels above, and a recipe listing
   the available area labels.
6. Write the model into the repo's `AGENTS.md`/`CLAUDE.md` in a few lines (base branch, labels, fixes-only
   `main`) — agents and new colleagues read that, not this skill.
7. Verify with a dry run per case: a labeled feature PR into `dev` runs only its areas (unit and E2E); a
   `dev` -> `test` PR skips tests but runs the build; a feature PR into `main` is rejected; a manual run of
   the scheduled pipeline runs everything and (on green) deploys to `test`.

## Gotchas

- **Azure Repos ignores `pr:` triggers in YAML.** For Azure Repos Git, PR builds come only from the *branch
  policy*; the `pr:` block is honored on GitHub only. So "has a build policy" really is the mechanism, not
  a nicety. Don't path-filter the policy in a way that lets a PR merge with no build at all.
- **PR builds run on the merge ref**, so `Build.SourceBranchName` is `merge`, not the branch name. Decide
  from `System.PullRequest.SourceBranch` / `TargetBranch` (runtime expressions, `$[ ... ]`), not from
  compile-time `${{ }}` templates.
- **A skipped stage still satisfies the policy**, a failed or cancelled one doesn't. Skip with a `condition`,
  never by failing early.
- **The nightly deploys the `dev` build to the `test` environment; it does not move the `test` branch.** The
  branch only advances through `dev` -> `test` PRs. Say so in the repo docs so nobody reads the `test`
  branch as "what's deployed on test".
- **Don't use `--bypass-policy`** to get a promotion through; a red promotion build means the build part is
  broken and should be fixed on `dev`. Fix conflicts on `dev` first and re-promote, rather than resolving
  them only in the promotion PR (the next promotion will conflict again).
- GitHub repos: same model, expressed as branch protection with required status checks on all three
  branches, `pull_request` workflows with `if` conditions mirroring the `executeTests` rule, and
  `on: schedule` on `dev`. `bdt pr` works identically on both hosts.
