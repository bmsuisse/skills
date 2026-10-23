# maintenance: xfail

Tests marked as expected to fail are debts: each one hides a bug or a missing feature, and a fixed one stays
hidden. Burn them down.

**Run per test project** (every dir with a `pyproject.toml` that has tests, plus e2e folders; see [bump.md](bump.md)
for finding them).

```bash
grep -rnE "xfail|test\.fail|test\.fixme|it\.fails|\.todo\(" tests* --include=*.py --include=*.ts --include=*.tsx
uv run pytest -rxX -p no:randomly <paths>        # x = still failing as expected, X = XPASS (fixed, marker stale)
```

Python's `-rxX` summary lists the xfails with their `reason`. Non-strict xfail passes silently as XPASS, so
the scan above, not a green run, is the inventory.

For each one, in this order:

1. **XPASS**: it passes, the marker is stale. Remove the marker. Several runs, if it is also flaky (see
   [tests.md](tests.md)), else you turn a flake into a red build.
2. **Reason names an issue**: read it. Closed and fixed: remove the marker and verify. Open: leave it, pick it
   up in this run only if the fix is small.
3. **No reason / no issue**: run it with the marker removed, read the failure, find out why. A real bug: fix it
   (the test is the reproducer) or `bdt issue create --title "..."` and put the number in the `reason`. A wrong
   test: fix the test. A feature that was never built: issue, keep the xfail with its number.
4. **Every remaining xfail has a `reason` with an issue number.** Add `strict=True` to each (or
   `xfail_strict = true` under `[tool.pytest.ini_options]`) so a fixed bug fails the build instead of rotting.

One commit per fixed test (marker removal together with the fix), so a revert is trivial. Don't fix a failing xfail by
loosening its assertion, and don't turn `xfail` into `skip`. Run the whole area's tests afterwards, not only the
touched file. In the PR: count before/after, the list of fixed ones, the ones left with issue links.
