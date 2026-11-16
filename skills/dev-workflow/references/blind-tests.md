# Tests first: contract tests (step 3b)

Tests written by the agent that also writes the code tend to mirror the code and get bent when they fail. Step 3b has a
separate agent (`bms-test-writer`) write them from the task and the plan before the implementation exists.

This is a process rule, not a lock. Nothing blocks an edit; the pre-publish review (step 8) checks that the tests are unchanged.

## When

Run it for any task that has an implementation plan (step 3). Skip it, and say so in the plan or PR, when:

- the change is a refactor and existing tests already pin the behaviour, or
- there is no new behaviour worth a committed test (see `testing-strategy`, "Not everything requires tests").

A bug fix from an issue is not a skip: the writer gets the issue and writes the failing reproduction.

## What the plan must contain

The writer has nothing else to go on, so `bms-plan-review` blocks a plan without:

- **Acceptance criteria**: observable behaviours, including the error cases that matter.
- **Contract**: routes with request/response shapes and status codes, function signatures, `data-testid`s for every UI element a flow touches, auth expectations.

## Steps

1. Dispatch `bms-test-writer` (foreground) with the worktree path, the task or issue text, the plan (path or PR comment), the layer(s) and where tests live.
2. `RESULT: blocked`, or any unresolved ambiguity in its report: fix the plan or ask the human **before** going on. Both agents share the same reading of the task, so this is the only point where a misreading is cheap to catch. Re-dispatch afterwards.
3. Check the report: every test maps to a criterion, every failure is at the expected point (not an import/setup error), the count is proportionate. Run the command it gives once yourself.
4. Commit the tests and any stubs in their own commit, message starting `test: contract tests`, and note its sha. Push.

## Implementing against them

- Don't edit the contract tests, their fixtures, seed data or test config to get green. Make the code pass.
- Add the `data-testid`s and fill in the stubs.
- Scratch tests (`test*_temp.py/ts`, gitignored) are still fine for your own exploration.
- A test or the plan looks wrong: stop that part of the work and post a change request with `bdt pr comment`:
  `Contract test change request: <test> — <what is wrong and why>`. The human decides. If they agree, update the plan, re-dispatch the writer with the reason, and commit its result as a new `test: contract tests` commit. Don't approve your own request.

## Check before publish (step 8)

Run `git diff <sha> -- <test paths and the files they depend on>` where `<sha>` is the last `test: contract tests` commit. The diff covers uncommitted changes too. Any difference needs an approved change request in the PR comments; otherwise treat it as a blocking finding. Also check the suite is still collected and run by CI (no deselected files, no new skip/xfail markers).

## Limits

The writer's "don't read the implementation" is an instruction, not a sandbox, and it only fully holds for new code. Two agents reading the same task can misread it the same way; the ambiguity list in step 2 is the mitigation. Codex has no `bms-test-writer`, so under Codex the main agent writes the tests itself and must follow the same rules.
