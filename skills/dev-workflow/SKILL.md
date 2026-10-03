---
name: dev-workflow
plugin: dev-workflow
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
   if unavailable). If the repo has a `justfile` with a `worktree` recipe, use
   `just worktree` to set it up instead of doing it by hand.
2. **Draft PR early.** Push the initial (even empty/WIP) commit and open a
   draft PR immediately using `bdt` (github/bmsuisse/devtools) — before doing
   the actual work. This gives CI and reviewers visibility from the start.
   If working from an issue, claim it as soon as the draft PR exists (it must
   say `Fixes #N`): run `bdt issue take` (or `bdt issue take N`). It comments
   `Taken by <you>` plus your session so the requestor knows it's being worked
   on, and does nothing if the issue's newest comment already is such a claim.
   Don't hand-write a session comment. If you were launched by `bdt issue do N`,
   the issue is already taken (with this session) — don't run it again.
3. **Implementation Plan**: If your task is more complex, you do an implementation plan first, and you also upload it to PR (using `bdt pr comment --file FILE`). You should usually start with Database, then Backend, then Frontend.
   Then run `/bms-plan-review` on the plan and address its findings before implementing.
4. **Implement** the task. If you find or fix a bug along the way, create an
   issue for it (`bdt issue create --title "..."` — prints just the issue
   link; even if you close it right away) and reference that link from a
   short comment at the fix site — don't inline lengthy explanations of the
   bug or how it was resolved in source code comments.
   Once a step is done, commit&push. Commit early, commit often.
   see `references/unrelated-bugs.md` if you spot a bug outside the current task's scope.
5. **Review (mid-work).** Run `/bms-code-review --quick` (or, where it isn't available, `/code-review low`) on the diff after a meaningful chunk and address findings. Cheap, but it only catches the most obvious issues — it is not the pre-publish review.
6. **Test.** Run a relevant subset of tests (not the full suite — that's CI's
   job) covering what changed.
7. **Screenshots.** If the change is visual/UI, capture before/after
   screenshots and attach them to the PR. Do screenshots for mobile and desktop.
   Then do a "/design-review" for the screenshots using a subagent and adress findings.
   If working from an issue, also post the screenshots as an update on the issue.
   Do not stop the Web server, ask human to click through changes and verify. once ok for human, proceed.
8. **Pre-publish review (always).** Run `/bms-code-review --full` on the whole diff (or, where it isn't available, `/code-review` at medium, or high for risky changes) and fix findings (ask if unsure). This is the review the PR-publish gate is really for; it is required even if the mid-work `--quick` review was clean, and especially for SQL, auth, concurrency or money handling.
9. **Publish** the PR via `bdt pr publish`, which will trigger CI
10. **Watch CI.** Run `bdt pr status --wait`. If remote checks fail, fix and
   push — don't just report the failure. `bdt pr info` gives the PR link,
   build state and closed issues in one quick call (the `bdt-status` plugin
   shows the same above the prompt).
11. If working from an issue, update it with a summary and implementation
   screenshots once the PR is up.
12. **Clean up.** Never merge the PR yourself — wait for a human to approve
    and merge it. Once it's merged, remove the worktree using `bdt cleanup worktree`

Full test-suite runs, broad regression sweeps, etc. are CI's responsibility —
don't run them locally unless asked.

