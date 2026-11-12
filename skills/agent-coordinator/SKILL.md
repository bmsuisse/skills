---
name: agent-coordinator
plugin: dev-workflow
description: >
  Coordinate several agents working in parallel on one repo: partition the work, give each agent a worktree off a
  policy-free consolidation branch, then ship everything in one PR to dev (one review, one CI run). Use when asked to
  "run agents in parallel", "split this across agents", "fan out" a multi-part change, or when you are about to
  spawn several implementers on the same repo.
---

# Agent coordinator

`dev-workflow` gives every task its own draft PR, review and CI run. With N agents on one repo that is N CI runs
on `dev`, mostly for half-finished slices. Here the agents integrate into a **consolidation branch** that has no
build policy, and the coordinator opens **one PR** from it into `dev` once everything has landed.

```
agent branch ─push─▶ consolidate/<topic> ──one PR (review, CI, labels)──▶ dev
agent branch ─push─▶       (no policy)
agent branch ─push─▶
```

Not for a single task (use `dev-workflow`) or for independent changes that should be reviewed, released or
reverted separately (separate PRs on purpose).

You are the coordinator: you plan, spawn, integrate and publish. You do not implement a slice yourself while
agents run.

## 1. Plan and partition

1. Split the work into tasks with **disjoint file ownership**. Two agents editing the same file is the main
   source of pain; if the split needs it, make that a sequential dependency instead.
2. Files nobody owns alone (lockfiles, generated API clients, migration numbering, route/registry lists,
   `pyproject.toml`) go to exactly one task, or you regenerate them yourself in step 4.
3. Order dependent work in waves, usually Database → Backend → Frontend (as in `dev-workflow` step 3). Agents in
   one wave run in parallel; start the next wave only after the previous one has landed.
4. Write the plan (tasks, owned paths, waves, the issues each task closes), run `/bms-plan-review` on it, and put
   it on the PR in step 2.
5. Keep it to roughly 3-5 agents per wave. More agents means more conflicts, and every worktree needs its own
   test DB and ports.

## 2. Consolidation branch and PR

1. `git fetch origin dev`, then create `consolidate/<topic>` from `origin/dev` and push it. (`bdt worktree`
   bases on the *local* `dev`, which is often stale; always fetch first.)
2. The branch must carry **no build policy**. Check on the first push; if a wildcard policy rejects it, stop and
   ask a human. Never use `--bypass-policy`. It is short-lived, never deployed, and only ever merged into `dev`
   through a policy-protected PR (see `branching-strategy`, rule 2).
3. Open the single draft PR `consolidate/<topic>` → `dev` right away with `bdt pr create --label test-full`
   (draft builds nothing; `bdt` demands a test label where `[tool.bdt.ci.plan]` is set, and `test-full` is the
   honest placeholder until step 5 narrows it). Keep the default squash and **delete source branch on completion**
   (don't pass `--delete-source-branch false`), so the branch is removed when the PR merges. Post the plan, and link
   **every** issue it closes (`Fixes #N` / `AB#N`, once per issue). Claim each issue with `bdt issue take N`;
   agents do not.

## 3. Spawn the agents

One agent per task, in parallel (a single message with several Agent calls). Brief each with
`references/agent-brief.md`: its worktree command, owned paths, what not to touch, how to integrate, and the
report format. The agent runs `dev-workflow` steps 1, 4, 5 and 6 (worktree, implement, `--quick` review,
targeted tests) and **skips** steps 2 and 7-12: no PR, no publish, no CI watch, no screenshots.

Each agent integrates by itself as soon as its task is done and green locally:
rebase onto `origin/consolidate/<topic>`, re-run its tests, push fast-forward only
(`git push origin HEAD:consolidate/<topic>`), and retry from the fetch on rejection. A conflict inside its own
paths it resolves; a conflict with another agent's paths it reports to you instead of guessing.

Agents never open, publish or merge PRs and never push to `dev`, `test` or `main`.

## 4. Integrate and verify

There is no CI on the consolidation branch, so you are the integration check:

- After each wave, fetch the branch in your own worktree and run the cheap checks: build, lint, type-check, and
  the tests of the areas the wave touched. Fix problems in that worktree or send the owning agent back; fixing
  only your own slice of a conflict is fine, rewriting an agent's work is not.
- Regenerate shared artifacts (step 1, point 2) once, after the last wave.
- Start the next wave from the verified tip.

## 5. One review, one publish

When all tasks have landed:

1. `git merge origin/dev` into the consolidation branch (merge, not rebase, so agent pushes stay valid) and
   re-run the checks.
2. Run `/bms-code-review --full` on the whole diff against `dev` (or a finished `codex` review, see
   `dev-workflow` step 8) and fix the findings. This is the only review the PR-publish gate sees, so do not skip
   it because each agent ran `--quick`.
3. UI changes: screenshots once, on the combined result (`dev-workflow` step 7).
4. Replace the placeholder label with the **union** of the test areas touched (`test-<area>`, or keep `test-full`
   when any agent touched shared code). Then `bdt pr publish`.
5. Watch CI with the `bms-ci-watch` agent. Every push to the branch re-triggers CI, so collect failures and
   push one fix, not one per failure. If a fix is large enough to parallelise, run it as a new wave with a fresh
   brief; the PR stays the same.

## 6. Clean up

Never merge the PR yourself. The consolidation branch is deleted when the PR merges (the completion option from
step 2; the squash means the agents' working history is not kept). Once a human has merged it, check
`git ls-remote --heads origin consolidate/<topic>`: if it is still there, delete it
(`git push origin --delete consolidate/<topic>`). Also remove every agent worktree with `bdt cleanup worktree`. Remove only your own worktrees; others in `.worktrees` may belong to other
sessions.

Link every PR and issue as a link, never a bare `#N`.
