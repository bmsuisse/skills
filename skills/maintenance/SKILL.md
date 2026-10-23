---
name: maintenance
plugin: maintenance
description: >
  Periodic repo upkeep for BMS Python (uv) and JS/TS (bun) repos, as one skill with a
  mode argument: `dead-code` (find/remove unused code), `bump` (update
  dependencies), `lint` (Python projects on the latest ruff/ty baseline of `init-app-stack`), `audit` (`bun audit` / `uv audit`
  vulnerability fixes), `prod` (Application Insights errors vs. open issues), `nightly` (failed nightly builds),
  `xfail` (fix xfail tests), `db-perf` (slow queries / Postgres health), `tests` (slow and flaky tests), or `all`.
  Use for "maintenance", "regular tasks", "find dead code", "remove unused code", "bump
  dependencies", "update packages", "ruff/ty baseline", "bun audit", "uv audit", "vulnerable
  dependency", "CVE", "Dependabot alert", "check prod logs", "app insights", "nightly failed", "xfail",
  "slow queries", "postgres performance", "flaky tests", "slow tests". Invoke as `/maintenance <mode>`. Repo-wide upkeep, not for
  reviewing a pending diff (deslop, security-review).
---

# Maintenance

`/maintenance dead-code | bump | lint | audit | prod | nightly | xfail | db-perf | tests | all`. No argument: ask which.
`all` runs them in the order `prod`, `nightly`, `xfail`, `tests`, `db-perf` (what is broken now, so the upkeep
runs against a known baseline), then `dead-code`, `bump`, `lint`, `audit` (remove first, so less is upgraded), one commit series per mode.
Work in a worktree and make a separate commit for each step of a mode (`/dev-workflow`). Use `uv` and `bun` only, never hand-edit lockfiles.

## Rule for bump, lint (version bumps) and audit: never lock

No `==` pins, `<` caps, `overrides`/`resolutions`/`override-dependencies`/`constraint-dependencies`,
`exclude-newer` or `--exact` to dodge an upgrade. Existing pins and caps stay (except one blocking an audit fix, see audit); mention stale-looking ones in the PR.
Can't upgrade? Leave the package where it is, `bdt issue create --title "..."`, link it in the PR.

Deterministic checks belong in `bdt` (devtools); this skill keeps the rules and the judgment.

## Modes

Read the reference for the requested mode, then follow it.

| Mode | Reference |
|---|---|
| `dead-code` | [references/dead-code.md](references/dead-code.md) |
| `bump` | [references/bump.md](references/bump.md) |
| `lint` | [references/lint.md](references/lint.md) |
| `audit` | [references/audit.md](references/audit.md) |
| `prod` | [references/prod.md](references/prod.md) |
| `nightly` | [references/nightly.md](references/nightly.md) |
| `xfail` | [references/xfail.md](references/xfail.md) |
| `db-perf` | [references/db-perf.md](references/db-perf.md) |
| `tests` | [references/tests.md](references/tests.md) |

`prod`, `nightly`, `db-perf` and the flaky half of `tests` mostly *find* things: their output is issues, with no duplicates.
Before creating one, `bdt issue search --state all --since-days 0 "<keywords>"`, and one issue per root cause. Only
small, clear fixes become PRs.

## PR

Per mode: what was removed / bumped (old → new, majors marked) / linted (config changes, rules enabled) / fixed (advisory id, severity), what was left behind
or excluded and why (issue link), checks run. For `prod`, `nightly`, `db-perf`, `tests`: what was checked, findings and the issue
links (new or existing), before/after numbers for fixes. Don't merge it yourself.
