---
name: maintenance
plugin: maintenance
description: >
  Periodic repo upkeep for BMS Python (uv) and JS/TS (bun) repos, as one skill with a
  mode argument: `dead-code` (find/remove unused code), `bump` (update
  dependencies), `audit` (`bun audit` / `uv audit` vulnerability fixes), or `all`.
  Use for "maintenance", "find dead code", "remove unused code", "bump
  dependencies", "update packages", "bun audit", "uv audit", "vulnerable
  dependency", "CVE", "Dependabot alert". Invoke as `/maintenance <mode>`.
---

# Maintenance

`/maintenance dead-code | bump | audit | all`. No argument: ask which. `all` runs them in the order
`dead-code`, `bump`, `audit` (remove first, so less is upgraded), one commit series per mode.
Work in a worktree and commit after each step (`/dev-workflow`). Use `uv` and `bun` only, never hand-edit lockfiles.

## Rule for bump and audit: never lock

No `==` pins, `<` caps, `overrides`/`resolutions`/`override-dependencies`/`constraint-dependencies`,
`exclude-newer` or `--exact` to dodge an upgrade. Existing pins stay; mention stale-looking ones in the PR.
Can't upgrade? Leave the package where it is, `bdt issue create --title "..."`, link it in the PR.

## Modes

Read the reference for the requested mode, then follow it.

| Mode | Reference |
|---|---|
| `dead-code` | [references/dead-code.md](references/dead-code.md) |
| `bump` | [references/bump.md](references/bump.md) |
| `audit` | [references/audit.md](references/audit.md) |

## PR

Per mode: what was removed / bumped (old → new, majors marked) / fixed (advisory id, severity), what was left behind
or excluded and why (issue link), checks run. Don't merge it yourself.
