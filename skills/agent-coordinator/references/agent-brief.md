# Agent brief (copy, fill in, send as the agent's prompt)

```
You are one of several agents working in parallel on <repo>. Task: <task, with the issue link>.
Coordinator plan: <link to the plan comment on the PR>.

Setup
- git fetch origin consolidate/<topic>
- bdt worktree <topic>-<task> --base origin/consolidate/<topic>   (or `git worktree add .worktrees/<topic>-<task> origin/consolidate/<topic> -b <topic>/<task>`)
- Confirm `git rev-list --count HEAD..origin/consolidate/<topic>` is 0. Work only inside that worktree.
  Do not share a test database or port with other worktrees.

Scope
- You own: <paths>. Do not edit anything else. If the task needs a change outside your paths, stop and report it.
- Do not touch lockfiles, generated clients or migration numbering unless listed above.

Work
- Follow dev-workflow steps 4-6: implement, commit often (explicit paths only), run `/bms-code-review --quick`
  on your diff after a meaningful chunk, run the tests for your area only (not the full suite; CI does that later).
- Before integrating, review your own work: `/bms-code-review --full` on your diff against
  `origin/consolidate/<topic>`, and fix the findings (ask the coordinator if unsure). The coordinator does not
  review your slice, so this is the only review it gets.
- Do NOT open, publish or merge a PR, do NOT run `bdt pr ...` or `bdt issue ...`, do NOT push to dev/test/main.

Integrate when done and green
- git fetch origin consolidate/<topic> && git rebase origin/consolidate/<topic>
- re-run your tests
- git push origin HEAD:consolidate/<topic>     (fast-forward only: never force; on rejection fetch, rebase, retest, push again)
- A conflict in files you own: resolve it. A conflict in files another agent owns: abort the rebase and report it.

Report (short)
- Result: landed | blocked. Commit range pushed. `--full` review done and findings fixed (yes/no, what was left). Test areas touched (for the PR labels).
- Anything you noticed outside your scope (do not fix it), and whether shared code was touched.
```
