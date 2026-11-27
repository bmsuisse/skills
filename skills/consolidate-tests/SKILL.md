---
name: consolidate-tests
plugin: coding
description: >
  Shrink a pytest suite to fewer, clearer tests with the same behavioural
  strength: parametrize copy-paste variants, merge duplicates, drop subsumed
  and dead tests, move repeated setup into fixtures, proven by coverage and a
  scoped mutation run. Use for "consolidate tests", "too many tests",
  "deduplicate tests", "clean up the test suite". Pytest only.
---

# Consolidate tests

Goal: fewer, clearer tests with the same (or better) behavioural strength.
Never trade coverage or assertion strength for line count. There is no target
for tests removed or LOC saved: the report shows them, nothing optimises them.

What to write in the first place is [testing-strategy](../testing-strategy/SKILL.md);
this skill only reshapes tests that exist. Two of its rules apply here:

- **Keep files small**: one file per endpoint or flow. Merging duplicates
  across files must not grow one giant test file; keep the survivor in the file
  of its endpoint or flow.
- **Tiers stay as they are**: testing-strategy calls committed unit tests
  optional, but consolidation never deletes a tier or moves tests between
  tiers. Retiring unit tests in favour of HTTP and e2e tests is a separate
  decision for the user, with its own coverage check.

## 0. Scope

Work on one directory or module at a time, never the whole suite in one go.
Pilot on a stable area: an area whose code is about to be rewritten is a bad
candidate (its tests will change anyway).

Never consolidate:

- golden, snapshot or approval tests (the file is the expectation);
- live, e2e or browser tests (each scenario is expensive on purpose);
- `xfail(strict=True)` tests with a reason: they record a known gap;
- tests in another layer (do not merge a unit test into an HTTP test or back).

## 1. Baseline (before touching anything)

- Detect the runner and its config (`pyproject.toml`, `setup.cfg`, `tox.ini`,
  `conftest.py`); use the repo's own commands (`just`, `make`) if it has them.
  Start what the tests need (a database, a container) first.
- Run the scoped directory with coverage and keep the result:
  `pytest <dir> -q --cov=<package> --cov-branch --cov-report=json:cov_before.json`
- Record: tests collected (`pytest <dir> --collect-only -q | tail -1`), runtime
  (`--durations=20`), test LOC.
- If tests already fail, stop and report them. Do not consolidate a red suite.

## 2. Find candidates

Per file, list candidates in these categories:

- **Copy-paste variants**: bodies differ only in literals, inputs or expected
  values -> one `@pytest.mark.parametrize` test with ids.
- **Duplicates**: same assertions on the same code path, maybe in other files -> keep one.
- **Subsumed tests**: assertions a strict subset of another test's on the same
  setup -> delete the weaker one.
- **Repeated setup**: identical arrange blocks -> a fixture in the module or
  `conftest.py`, narrowest sensible scope.
- **Tiny single-assert tests** on one object: combine when they share setup and
  describe one behaviour; keep them apart when the behaviours differ.
- **Classes with no shared state** -> functions, if that is the repo's style.
- **Dead tests**: skipped forever, `xfail` with no reason, testing removed code -> propose deletion.

A per-test coverage map helps: `pytest <dir> --cov=<package> --cov-context=test --cov-report=`,
then `coverage json --show-contexts`. Tests covering exactly the same lines and
branches are strong duplicate candidates. Still read them: same lines is not
the same assertions.

Before deleting or renaming a test file or a test, grep the whole repo for its
path and name: docs, agent files, skills and CI configs often point to tests.

Show the candidate list (by file, with estimated tests and LOC removed) to the
user before large edits. Small, obvious parametrizations can go ahead directly.

## 3. Rewrite rules

- Preserve every distinct assertion: a merged test asserts the union of what
  the originals asserted.
- **A regression test keeps its identity**: its name or bug reference survives
  as the `id` of its parameter (`pytest.param(..., id="issue-123-empty-month")`)
  or it stays a test of its own.
- Parametrize with readable ids so a failure names its case.
- One test = one behaviour. Parametrizing inputs is good; chaining unrelated
  scenarios in one function is not.
- Keep edge cases (None, empty, boundaries, error paths) as explicit params.
- Errors: `pytest.raises` inside the parametrized test, or a separate
  parametrized error test.
- Respect the repo's conventions: naming, markers, fixture style, session
  fixtures (Spark, Databricks, a test database).
- Do not change production code. If the code's design makes a test hard to
  consolidate, note it instead.
- Work file by file and run that file's tests after each change.

## 4. Verify (mandatory)

- The scoped directory is green, then the full suite once at the end.
- Run it once in random order (`pytest-randomly`, or `-p randomly` with two
  seeds): a fixture whose scope was widened can make tests depend on order.
- Coverage again (`--cov-report=json:cov_after.json`): compare line and branch
  coverage per module with `cov_before.json`. Fix any drop or justify it to the user.
- **Mutation check for every deletion or merge**: run a mutation tool (`mutmut`,
  `cosmic-ray`) on the modules whose tests lost a case, before and after. The
  surviving mutants must not increase. Pure parametrizations that delete no
  case can skip it.
- Runtime is not worse (fixture scope mistakes slow things down).

## 5. Report

| Metric | Before | After |
|---|---|---|
| Tests collected | | |
| Test LOC | | |
| Line / branch coverage | | |
| Surviving mutants (scoped) | | |
| Runtime | | |

Then list what was parametrized, merged and deleted (and why), and the tests
deliberately left alone. Commit one file or one category at a time so each
change is easy to review and revert.
