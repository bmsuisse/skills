# maintenance: tests

Slow, flaky and pointless tests. Slow ones make people skip the suite, flaky ones teach them to ignore red, pointless ones
only cost run time and upkeep. **Run per test
project** (see [bump.md](bump.md) for finding them); needs the test DB up (`pgdevkit`) like the normal run.

## Slow

```bash
uv run pytest --durations=25 --durations-min=1.0 -p no:randomly <paths>           # slowest tests *and* setup/teardown
bunx playwright test --reporter=json > pw-report.json                               # per-test duration in the report
```

Playwright: sort `suites[].specs[].tests[].results[].duration` of the JSON report (or open the HTML report). Look at
setup/fixture time as well as test time: a slow fixture is paid by every test using it.

Typical causes, cheapest fix first: a function-scoped fixture that should be session/module-scoped (DB creation,
app startup, login: do it once, then clean per test by transaction rollback or truncating); `sleep`/fixed timeouts
instead of waiting on a condition (`expect(...)` / `page.wait_for_*`); an e2e test that checks what an HTTP-level
test could (`testing-strategy`); real network or Azure calls that should be faked; a missing index on the test DB
(see [db-perf.md](db-perf.md)). Don't delete a slow test to make the suite faster, and don't weaken what it asserts.
Report total suite time before/after and the top 10 before/after.

## Flaky

A test is flaky if it fails and passes on the same commit. Sources of evidence: nightly runs
([nightly.md](nightly.md)), PR builds that went green after a retry (`bdt pr retry` history), and the suite itself:

```bash
for i in 1 2 3 4 5; do uv run pytest -p no:randomly -q -x <paths> || echo "run $i failed"; done   # same order, 5 times
uv run pytest -p randomly -q <paths>                                                              # order dependence (pytest-randomly)
bunx playwright test --repeat-each=10 --retries=0 <spec>                                          # one e2e spec, no hidden retries
```

Run a suspect alone, then with its neighbours: passes alone and fails in the suite means shared state or order.
Common causes: shared or leaked state between tests (module globals, DB rows, files, env vars); time and timezone
(`now()`, midnight, DST); ordering assumptions (no `order by`, dict/set order); race conditions and fixed waits
in e2e; port or file collisions between parallel workers; data that depends on the date.

Fix the cause. Not: more retries, longer sleeps, `--reruns` (that hides it), or `xfail`. A flake you can't pin down
in reasonable time: `bdt issue create --title "..."` (failure output, how often, what you ruled out; search first, no
duplicates) and, only then, quarantine it with an explicit marker that names the issue, so it is visible and not
silently green. In the PR: which tests, the cause, and how you verified (N consecutive green runs).

## Pointless

`testing-strategy` ("Not everything requires tests"): a committed test covers at least ~100 lines of real code, a
complex algorithm, or a real user interaction in e2e. **Remove the ones that don't**: they cost time on every run and
break on every refactor without catching anything. Candidates:

- tests that only restate the code: a getter/setter, a constant, a thin wrapper, a mock returning what the test
  then asserts, a model accepting its own fields, `assert f(x) == <the same expression as in f>`;
- tests with no assertion that matters (only "doesn't raise" on a trivial call) or that assert on mocks, not behaviour;
- two tests of the same tier with the same flow and different names, or the same assertions repeated across cases. An
  HTTP test plus an e2e spec of the *same flow* is the intended pairing of `testing-strategy`: keep it, but trim the e2e
  spec's backend assertions if it re-checks what the HTTP test does;
- committed `test*_temp.py` / `test*_temp.ts` scratch files: delete them and make sure `.gitignore` has the
  `test*_temp.*` patterns.

Find them by reading, with coverage as a hint (needs `pytest-cov`: `uv add --dev pytest-cov` if missing, don't commit it just for this):
`uv run pytest --cov --cov-context=test`, then `uv run coverage json --show-contexts` writes `coverage.json` with, per line,
which tests ran it; a test whose own lines (outside shared fixtures and imports) number a handful is a
candidate, not a verdict. Read each candidate before deleting.

**Keep**, however short: a test that pins a fixed bug (the issue or commit says so), an auth/permission rule, a money or
rounding calculation, a migration/constraint guarantee. Unsure: keep it, and list it in the PR for a human.
Delete one logical group per commit (the test and the fixtures/helpers only it used), run the suite, and report the
count removed, suite time before/after, and the coverage delta. It should barely move; a larger drop means a test
covered something: check whether that code needs a real test (write one) or is dead (remove it). Dead code that only a removed test still called goes through [dead-code.md](dead-code.md).
