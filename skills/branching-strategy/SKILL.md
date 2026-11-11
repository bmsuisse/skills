---
name: branching-strategy
plugin: dev-workflow
description: Set up or audit a repo's dev -> test -> main branching, build policies, per-area test labels and nightly deploy.
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
   thinking. `test` and `main` only ever receive promotions (plus fixes to `main`, rule 7). The one
   exception to "branch off `dev`" is a production fix, which branches off `main`.
2. **`dev`, `test` and `main` all carry a build policy.** Required, blocking, no direct pushes. It matters
   on `test` and `main` even though tests are skipped there: it forces every change through a PR, it still
   runs the build/lint/type-check part of the pipeline, and it gives one place that says "this was verified"
   before a deploy. A branch without the policy is a branch anyone can push untested code into.
   Deploys to `test` and `main` additionally need **approvers on the pipeline's environment** (a human
   signs off the deploy itself); that is configured on the environment, not in the YAML or a script —
   see `references/azure-devops-policies.md` (which also covers giving the unattended nightly its own
   approval-free environment, if wanted).
3. **Tests are split by product area, and the PR itself decides which areas run, through labels.** Both
   unit and E2E tests live in per-area folders (`tests/unit/<area>/`, `tests/e2e/<area>/`). Each area has a
   label `test-<area>`, plus `test-full` for broad/cross-cutting changes and `test-none` for changes no test
   covers. The author labels the PR with every area the change touches; CI runs only those folders, in both
   tiers. `bdt` required labels (below) make a PR impossible to create without that decision, and `bdt ci plan`
   (below) turns the labels into the test selection: a PR opened without a usable label gets its areas inferred
   from the changed files. Lint, type-check and the build are cheap and area-agnostic: they run in full on every PR.
4. **Promotion PRs run no tests.** The three promotions `dev` -> `test`, `test` -> `main` and `main` -> `dev`
   skip the test stages: the code was tested when it entered `dev` and again in the nightly run. The build
   policy still applies; the plan step selects no tests and the test stages are skipped. They need no code review either:
   the code was reviewed when it entered `dev`, and the `dev-workflow` PR-publish gate lets them through
   without a `/bms-code-review` run.
5. **A nightly build on `dev` runs the complete suite** (every area, unit and E2E) and, only if green,
   deploys `dev` to the `test` environment. It is the safety net for the per-area shortcut in rule 3: a
   change labeled `test-visits` that quietly broke `customers` is caught here, not in production. Run it
   even when `dev` hasn't changed (`always: true`), because drift in data, dependencies and the environment
   breaks tests too.
6. **Promotion order is `dev` -> `test` -> `main`.** No skipping `test`. Opening the `dev` -> `test` PR is
   what a human does when `test` is needed sooner than the nightly, or to mark a release candidate.
7. **PRs into `main` are only allowed for fixes.** Two shapes qualify: the promotion `test` -> `main`, and a
   fix branch (`fix/...` or `hotfix/...`) for something broken in production, **cut from `main`** so it
   doesn't drag unreleased `dev` work into production. A fix branch is *not* covered
   by rule 4 — its code hasn't been tested anywhere yet — so it runs tests like any other PR, with labels, and `bdt ci plan` checks that it was cut from `main`.
   After it merges, merge `main` back into `dev` (a `main` -> `dev` promotion PR, no tests) so the fix
   isn't lost or reverted by the next promotion. Features, refactors and chores never target `main`.

### What runs where

| PR / build | Lint, types, build | Unit + E2E | Build policy |
|---|---|---|---|
| feature -> `dev` | all | areas from labels (inferred if unlabeled) | yes |
| fix -> `main` | all | areas from labels (inferred if unlabeled) | yes |
| `dev` -> `test`, `test` -> `main`, `main` -> `dev` | all | skipped | yes |
| push to `test` / `main` (after merge) | build | skipped | deploys to its environment |
| nightly on `dev`, or any manual run (also on `test` / `main`) | all | **all areas** | nightly: then deploys `dev` to `test` env |

A PR from a feature branch into `test` is a mistake, not a variant: it would put untested code on `test`.
`bdt ci plan` fails the build for it, same as for rule 7.

## Splitting tests by area

- An *area* is a product feature area (`customers`, `orders`, `route_planning`), the same vocabulary in both
  tiers. Use the same folder name in `tests/unit/` and `tests/e2e/`; an area that exists in only one tier is
  fine (that tier is simply skipped for it).
- Keep a `shared` area for specs that belong to no single feature (responsive/UI audits, cross-cutting
  helpers' own tests). It is an ordinary area (`test-shared`); area folders must not be called `full` or `none`.
- Move tests into the area that owns the *behaviour*, not the file that happens to be imported. A unit test
  of a pricing function belongs to `orders` if orders is what breaks when pricing breaks.
- Don't hand-split a flat test suite in one go. Start with the largest or slowest files, map them to areas with
  the glob table below, let the rest fall into `shared`, and move tests as they are touched; the nightly run
  covers the transition.
- Shared code (auth, layout, API client, DB schema, config, dependencies) is not owned by any area, so
  changing it means `test-full` (inference does the same for an unlabeled PR: any non-test, non-`non_code` file
  selects everything). Say that in the repo's contributor notes.

## Required labels with `bdt`

With a `[tool.bdt.ci.plan]` table in `pyproject.toml` (below), `bdt pr create` requires at least one label of
the group `test_area` before it creates the PR. The group is **generated from the test folders** (`test-<area>`
for every area, which includes `test-shared` once a `shared` area exists, plus `test-full` and `test-none`),
so there is no list to keep in sync. A hand-written `[tool.bdt.pr.required_labels] test_area = [...]` still wins; only write one for a custom set.

```toml
# Optional: auto-add the label from the commit scope, so `feat(orders): ...` -> test-orders
[tool.bdt.pr.scope_labels]
orders = "test-orders"
```

- Area folder `snake_case` -> label `kebab-case` (`route_planning` -> `test-route-planning`).
- The check is global, not per target branch, so promotion PRs need a label too. Give promotion recipes a
  default of `test-none` (e.g. `bdt pr create --target test --label test-none`): they run no tests, so it is the
  honest label. Put the three flows in the repo's task runner (`pr-dev`, `pr-test`, `pr-main`) so nobody types
  branch names, plus a recipe that lists the area labels.
- Labels are the author's declaration, so judge them honestly: label every area the diff touches, and use
  `test-full` for shared code. `test-none` is for changes no test reads or ships (docs, repo chores). When
  unsure, go broader — a slow PR costs minutes, a missed regression is paid for in production.
- A new area is one edit: the `tests/{unit,e2e}/<area>/` folder (a sub-folder with tests).
- `bdt` blocks creation locally. A PR opened in the portal, or a label removed later, skips `bdt`; the
  pipeline then infers the areas from the changed files, or fails the build with `on_missing = "fail"`. If the
  pipeline can't read the labels or the change list, it runs the full suite rather than silently nothing.
- Legacy `e2e-<area>` labels keep working as aliases for `test-<area>`; one label selects the area's unit *and*
  E2E tests.

## Test selection with `bdt ci plan`

One step in the pipeline (`references/pipeline.md`) decides which tests run, instead of a hand-written script per repo. Pin
`bmsdna-devtools>=0.50.0` as a **dev** dependency and run `uv run bdt ci plan`. Config (an empty table selects
the defaults):

```toml
[tool.bdt.ci.plan]
on_missing = "infer"            # PR without a usable label: infer from the changed files (default) or "fail"
non_code = ["docs/**", "*.md"]  # files no test reads or ships; full-match globs (`*.md` = root only)

[tool.bdt.ci.plan.tiers.unit]   # default tiers: unit = tests/unit, e2e = tests/e2e
dir = "tests/unit"              # areas = sub-folders with tests

[tool.bdt.ci.plan.tiers.e2e]
dir = "tests/e2e"               # flat folder: map the test files to areas instead
areas = { chat = ["test_chat*.py"], review = ["test_review_*.py"] }  # unmatched files form the area `shared`
```

Order of decision (the step logs the reason):

1. Not a PR: the CI run after a push to `test` / `main` runs nothing. The nightly, manual runs (also on
   `test` / `main`), other branches and forks run everything.
2. Branch flow: promotions run nothing; `fix/*` / `hotfix/*` into `main` are tested and must be cut from `main`
   (needs `fetchDepth: 0`; skipped with a warning in a shallow checkout); any other PR into `test` / `main`
   fails the build.
3. Labels decide. Without a usable one the changed files do: only `non_code` -> nothing, only area tests ->
   those areas, anything else -> everything.
4. Anything unreadable runs everything.

Outputs: `runTests`, and per tier `<tier>Run`, `<tier>Areas`, `<tier>Paths`. A tier you don't split by area
(e.g. flat unit tests) is simply gated on `runTests`.

## Merge strategy with `bdt`

Squash feature work, never promotions (rule 4's definition: squashing `dev` -> `test` -> `main` leaves the same
content in different commits, so every later promotion conflicts again). `bdt pr create` (devtools >= the release
containing [bmsuisse/devtools#116](https://github.com/bmsuisse/devtools/pull/116)) applies this by default, so
the recipes need no flags:

- A PR whose **source** is a long-lived branch (`dev`, `develop`, `test`, `main`, `master`, `release/*`; so
  promotions and the `main` -> `dev` back-merge) gets a merge commit and its source branch is kept.
- Any other source (feature, `fix/...`, `hotfix/...`) is squashed and its source branch deleted on completion
  (Azure DevOps completion options; on GitHub only the auto-merge method is set, deleting branches is the
  repo's "automatically delete head branches" setting).
- The rule is by *source* branch, not target, so a `fix/...` -> `main` PR squashes while `main` -> `dev` does not.
- Different long-lived branches: `[tool.bdt.pr] long_lived_branches = ["dev", "test", "main", "staging"]`
  (case-insensitive globs; replaces the default list).
- Opt out per PR with `--squash false` / `--delete-source-branch false`, e.g. for a stacked PR whose source is
  another open PR's target (not detected).

Still set the repo's merge-strategy *policy* per branch (`references/azure-devops-policies.md`), so a PR
opened in the portal follows the same rule; `bdt` only covers PRs it creates.

## Setting a project up — checklist

1. Branches: create `dev` and `test` from `main` if missing; set `dev` as the default branch.
2. Test layout: split unit and E2E tests into `tests/unit/<area>/` and `tests/e2e/<area>/`. Add
   `[tool.bdt.ci.plan]` to `pyproject.toml` (and optionally `scope_labels`), and `bmsdna-devtools>=0.50.0` as a
   dev dependency.
3. Pipeline (`references/pipeline.md`): `UV_NO_BUILD=1` variable, a `Plan` stage running `bdt ci plan` (checkout with `fetchDepth: 0`), unit and
   E2E stages gated on its outputs (pytest with `--maxfail=3` to stop early and `--durations=20
   --durations-min=1.0` to log the slowest tests), compile-time variables only for environment and deploy, a
   nightly schedule on `dev` that runs everything and deploys to `test` when green, and deploy-only runs for
   pushes to `test`/`main`.
4. Policies (`references/azure-devops-policies.md`): build validation on `dev`, `test`, `main` pointing at that
   pipeline; reviewer minimums; no bypass. Plus approvers on the `Test` and `Production` environments the
   deploy job uses (documented there; set in the portal).
5. Task-runner recipes `pr-dev` / `pr-test` / `pr-main` (promotions default to `test-none`), and a recipe listing
   the available area labels. Squash/delete-source need no flags (see "Merge strategy with `bdt`").
6. Write the model into the repo's `AGENTS.md`/`CLAUDE.md` in a few lines (base branch, labels, fixes-only
   `main`) — agents and new colleagues read that, not this skill.
7. Verify with a dry run per case: a labeled feature PR into `dev` runs only its areas (unit and E2E; try
   `uv run bdt ci plan --pr-source feat/x --pr-target dev --label test-orders` locally); an unlabeled one gets
   its areas inferred; a `dev` -> `test` PR skips tests but runs the build; a feature PR into `main` is rejected; a manual run of the
   pipeline on `dev` behaves like the nightly (runs everything and, on green and after approval,
   deploys to `test`).

## Gotchas

- **Azure Repos ignores `pr:` triggers in YAML.** For Azure Repos Git, PR builds come only from the *branch
  policy*; the `pr:` block is honored on GitHub only. So "has a build policy" really is the mechanism, not
  a nicety. Don't path-filter the policy in a way that lets a PR merge with no build at all.
- **PR builds run on the merge ref**, so `Build.SourceBranchName` is `merge`, not the branch name. In your own conditions decide
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
- **uv never builds wheels: set `UV_NO_BUILD=1` as a pipeline variable** (`references/pipeline.md`; the
  per-command equivalent is `--no-build`). A dependency without a wheel for the pinned Python then fails
  the build instead of silently compiling from source (slow, needs a toolchain on the agent, not
  reproducible). Fix it by upgrading to a release that ships a wheel (e.g. a new Python version often needs
  bumped dependencies) or by dropping the dependency, not by allowing builds.
- GitHub repos: same model, expressed as branch protection with required status checks on all three
  branches, `pull_request` workflows whose `if` conditions skip tests on promotions, and `on: schedule` on
  `dev`. `bdt pr` works identically on both hosts; `bdt ci plan` reads Azure Pipelines variables and the Azure
  DevOps label API.
