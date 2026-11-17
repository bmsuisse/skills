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

Under Codex, dispatch agents from their card in `references/codex-agents/<name>.md`.

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
   Then, where you have a `Monitor` tool (Claude Code), run `bdt issue watch N --follow --skip-own --json`
   in it (persistent): each output line is a new comment from someone else. Reply with `bdt issue comment add`.
3. **Implementation Plan**: If your task is more complex, you do an implementation plan first, and you also upload it to PR (using `bdt pr comment --message-file FILE`). You should usually start with Database, then Backend, then Frontend.
   Then run `/bms-plan-review` on the plan and address its findings before implementing.
3b. **Tests first.** For a task with a plan (or a bug fix from an issue), dispatch the `bms-test-writer` agent (foreground) with the task, the plan and the layer(s): it writes contract tests from the acceptance criteria and contract, without seeing the implementation, and checks they fail for the right reason. Resolve every ambiguity it lists, commit the tests (`test: contract tests`), push. Details, skip rules and the change-request protocol: `references/blind-tests.md`.
4. **Implement** the task. Don't edit the contract tests (or their fixtures/config) to get green; if one looks wrong, post a change request instead. Keep comments at a fix site short — don't inline
   lengthy explanations of a bug or how it was resolved in source code comments.
   Once a step is done, commit&push. Commit early, commit often.
   see `references/unrelated-bugs.md` if you spot a bug outside the current task's scope.
5. **Review (mid-work).** Run `/bms-code-review --quick` (or, where it isn't available, `/code-review low`) on the diff after a meaningful chunk and address findings. Cheap, but it only catches the most obvious issues — it is not the pre-publish review.
6. **Test.** Run the contract tests plus a relevant subset of the rest (not the full suite — that's CI's
   job) covering what changed.
7. **Screenshots.** If the change is visual/UI, capture before/after
   screenshots and attach them to the PR. Do screenshots for mobile and desktop.
   Dispatch the `bms-design-review` agent (foreground; worktree path, app URL, pages and PR id in the prompt): it
   captures, runs `/design-review` and attaches in its own small context and returns only findings as text. Don't run
   the browser loop (navigate, resize, screenshot, retry) in your own thread: each turn re-reads your whole context.
   Address the findings and re-dispatch to re-check. Where agents aren't available, capture and run `/design-review` yourself.
   If working from an issue, also post the screenshots as an update on the issue.
   Do not stop the Web server, ask human to click through changes and verify. once ok for human, proceed.
8. **Pre-publish review (always).** If step 3b ran, first check the contract tests are unchanged (`git diff <tests-commit> -- <test paths>`, see the reference); a difference without an approved change request is blocking. Then run `/bms-code-review --full` on the whole diff (or, where it isn't available, `/code-review` at medium, or high for risky changes) and fix findings (ask if unsure). A finished review by another agent also satisfies the gate: `codex exec -C <dir> -s read-only "Use the bms-code-review skill (--full) on the diff ..." < /dev/null` (foreground with nothing piped or chained after it that could hide a failure, i.e. no `| tee`, `; echo` or `|| true`; or backgrounded with `&` and `-o <file>`), or `codex review`; see `bms-code-review`, "Running it through codex". Promotion PRs (source and target both in `dev`/`test`/`main`, see `branching-strategy`) are exempt: skip this step for them. This is the review the PR-publish gate is really for; it is required even if the mid-work `--quick` review was clean, and especially for SQL, auth, concurrency or money handling.
9. **Publish** the PR via `bdt pr publish`, which will trigger CI
10. **Watch CI.** Dispatch the `bms-ci-watch` agent (foreground, worktree path in the prompt): it runs
    `bdt pr status --wait` cheaply and answers `RESULT: green|red|cancelled|conflicts|abandoned|needs-approval|still-running` (plus a `MERGED:` line once the PR is merged: then do step 11, if it applies, and step 12's cleanup now). Don't poll in
    your own thread (`sleep`, a `Monitor` on the build, build API): every poll re-reads your whole context. If checks fail,
    fix, push and dispatch again; on `conflicts` rebase onto the target first, on `cancelled` find out why before re-running (`bdt pr info`), on `abandoned` stop and ask the user. When spawning isn't available, run `bdt pr status --wait --timeout 540` yourself and
    re-run it on exit 4 (still running). `bdt pr info` gives the PR link, build state and closed issues. A hook denies hand-written watch scripts (`az repos pr show`/`az pipelines runs`/build-API `curl`, `sleep` loops); if `bdt` is missing, `uv tool install bmsdna-devtools`.
11. If working from an issue, update it with a summary and implementation
   screenshots once the PR is up.
12. **Clean up.** Never merge the PR yourself — wait for a human to approve
    and merge it. Stop the issue-comment monitor (step 2) when you finish. Once it's merged, remove the worktree using `bdt cleanup worktree`

**Always link PRs and issues.** Whenever you mention a PR or issue number anywhere (PR descriptions, comments,
issue updates, commit messages, replies to the user), write it as a link, never a bare `#N`.

Several agents on the same repo: don't give each its own PR to `dev`. Use `agent-coordinator` (consolidation branch,
one PR, one CI run).

Full test-suite runs, broad regression sweeps, etc. are CI's responsibility —
don't run them locally unless asked.

