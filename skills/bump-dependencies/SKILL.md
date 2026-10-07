---
name: bump-dependencies
plugin: maintenance
description: >
  Bump Python (uv) and JS/TS (bun) dependencies in a BMS repo in small verified
  steps, without pinning or locking versions. Use for "bump dependencies",
  "update packages", "upgrade deps", "we're behind on dependencies". Not for
  vulnerability fixes (audit-dependencies) or removing unused packages
  (dead-code-analysis).
---

# Bump dependencies

Upgrade to current versions, keep the repo free to float.

## Rules

- **Never lock.** No `==` pins, `<` caps, `overrides`/`resolutions`/`override-dependencies`/`constraint-dependencies`,
  `exclude-newer` or `--exact` to dodge an upgrade. Existing pins stay; mention stale-looking ones in the PR.
- Never hand-edit `uv.lock` / `bun.lock`. Use `uv` and `bun` only.
- Work in a worktree, commit after each step (`/dev-workflow`).

## Python

```bash
uv tree --outdated --depth 1 --all-groups
uv lock --upgrade && uv sync
```

Raise lower bounds in `pyproject.toml` to the locked versions (`uv add "pkg>=X.Y"`), keep the existing specifier style.
A major excluded by the range: widen that one specifier, upgrade it in its own commit.
Also `uvx prek autoupdate` if the repo uses prek.

## JS / TS

```bash
bun outdated                 # -r in workspaces
bun update                   # within package.json ranges: commit
bun update --latest <pkg>    # majors: one package/ecosystem per commit
```

No blanket `--latest`. Keep caret ranges. If a stray `package-lock.json`/`yarn.lock` sits next to `bun.lock`, flag it.

## Verify per step

Type check, lint, relevant tests (`uv run ty check`, `bun run tsc --noEmit`); `bun run build` for frontend majors.
Read the changelog before every major.

## If it breaks

1. Fix the code to the new API (normal case).
2. Migration too big: leave that package at its version, **don't pin**, `bdt issue create --title "..."` and link it in the PR.
3. Upstream regression: say so in PR and issue, don't cap.

## PR

List bumped packages (old → new, majors marked), packages left behind with issue link, checks run. Don't merge.
