---
name: dev-workflow
plugin: coding
description: >
  End-to-end workflow for non-trivial coding tasks: worktree, draft PR early,
  implement, review, test, publish. Trigger whenever starting a task that's
  more than a trivial one-file fix — "implement X", "fix issue #N", "build
  feature Y" — or when the user says "follow the workflow", "use a worktree",
  or references `bdt`/`just workflow`.
---

# Dev workflow

For anything bigger than a trivial fix, follow this sequence. Skip steps only
when the tool genuinely isn't available (say so).

1. **Worktree.** Create one for the task (`EnterWorktree`, or `git worktree add`
   if unavailable). If the repo has a `justfile` with a `workflow` recipe, use
   `just workflow` to set it up instead of doing it by hand.
2. **Draft PR early.** Push the initial (even empty/WIP) commit and open a
   draft PR immediately using `bdt` (github/bmsuisse/devtools) — before doing
   the actual work. This gives CI and reviewers visibility from the start.
   If working from an issue, immediately comment on it with the session id
   (and PR link) so the requestor knows it's being worked on.
3. **Implement** the task. If you find or fix a bug along the way, create an
   issue for it (even if you close it right away) and reference that issue
   from a short comment at the fix site — don't inline lengthy explanations
   of the bug or how it was resolved in source code comments.
4. **Review.** Run `/code-review` on the diff and address findings.
5. **Test.** Run a relevant subset of tests (not the full suite — that's CI's
   job) covering what changed.
6. **Screenshots.** If the change is visual/UI, capture before/after
   screenshots and attach them to the PR. If working from an issue, also post
   the screenshots as an update on the issue.
7. **Publish** the PR (mark ready for review) via `bdt`.
8. **Watch CI.** Run `bdt pr status --wait`. If remote checks fail, fix and
   push — don't just report the failure.
9. If working from an issue, update it with a summary and implementation
   screenshots once the PR is up.

Full test-suite runs, broad regression sweeps, etc. are CI's responsibility —
don't run them locally unless asked.
