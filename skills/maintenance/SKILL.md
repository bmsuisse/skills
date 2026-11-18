---
name: maintenance
plugin: maintenance
description: >
  Periodic upkeep of BMS uv/bun/Gradle repos, one mode per run: dead-code, bump, lint, audit, prod, nightly, xfail, db-perf,
  cost, tests, incident (security incident / supply chain attack), all. Use for "maintenance", "bump dependencies",
  "bun audit", "uv audit", "CVE", "nightly failed", "slow queries", "azure cost spike", "flaky tests". Invoke as
  `/maintenance <mode>`. Not for reviewing a pending diff.
---

# Maintenance

`/maintenance dead-code | bump | lint | audit | prod | nightly | xfail | db-perf | cost | tests | incident | all`. No argument: ask which.
`all` runs them in the order `prod`, `nightly`, `xfail`, `tests`, `db-perf`, `cost` (what is broken now, so the upkeep
runs against a known baseline), then `dead-code`, `bump`, `lint`, `audit` (remove first, so less is upgraded), one commit series per mode. `incident` is event-driven and never part of `all`.
Work in a worktree and make a separate commit for each step of a mode (`/dev-workflow`). Use `uv` and `bun` only (Gradle: the wrapper), never hand-edit lockfiles.

## Rule for bump, lint (version bumps) and audit: never lock

Don't freeze a dependency at a version in `pyproject.toml` / `package.json` to dodge an upgrade: no `==` pins, `<` caps,
`overrides`/`resolutions`/`override-dependencies`/`constraint-dependencies`, `--exact`, or an *absolute* `exclude-newer`
date. Existing pins and caps stay (except one blocking an audit fix, see audit); mention stale-looking ones in the PR.
Can't upgrade? Leave the package where it is, `bdt issue create --title "..."`, link it in the PR.

The **dependency cooldown** is not a lock: a rolling, relative `exclude-newer = "5 days"` (uv) / `minimumReleaseAge` (bun)
names no version and moves with time; it only defers *brand-new* releases (see [bump.md](references/bump.md#cooldown)).
Gradle has no such setting: there it is `bdt deps cooldown` (see [bump.md](references/bump.md#gradle)).
Keep it, never remove it to get an upgrade through; a security fix younger than the cooldown goes through the exception
flow in [audit.md](references/audit.md#fixes-younger-than-the-cooldown).

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
| `cost` | [references/cost.md](references/cost.md) (uses the `azure-cost` skill) |
| `tests` | [references/tests.md](references/tests.md) |
| `incident` | [references/incident.md](references/incident.md) |

`prod`, `nightly`, `db-perf`, `cost` and the flaky half of `tests` mostly *find* things: their output is issues, with no duplicates.
Before creating one, `bdt issue search --state all --since-days 0 "<keywords>"`, and one issue per root cause. Only
small, clear fixes become PRs.

## PR

Per mode: what was removed / bumped (old → new, majors marked) / linted (config changes, rules enabled) / fixed (advisory id, severity), what was left behind
or excluded and why (issue link), checks run. For `prod`, `nightly`, `db-perf`, `cost`, `tests`: what was checked, findings and the issue
links (new or existing), before/after numbers for fixes. Don't merge it yourself.
