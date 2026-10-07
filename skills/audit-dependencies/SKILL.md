---
name: audit-dependencies
plugin: maintenance
description: >
  Check a BMS repo's dependencies for known vulnerabilities with `bun audit` and
  `uv audit`, and fix them by upgrading, without pinning or locking versions.
  Use for "audit dependencies", "bun audit", "uv audit", "vulnerable
  dependency", "CVE", "Dependabot alert". Not for general bumps
  (bump-dependencies) or reviewing our own code (security-review).
---

# Audit dependencies

Fix known-vulnerable dependencies by upgrading. Needs network (advisory databases).

## Rules

- **Never lock.** No `==` pins, `<` caps, `overrides`/`resolutions`/`override-dependencies`/`constraint-dependencies`,
  `exclude-newer` to force a version. A direct dependency needs a major? Bump it properly (`/bump-dependencies`).
- Ignoring is not fixing: only with a reason and issue link in the PR, and only if the code path is unreachable.
  Prefer `uv audit --ignore-until-fixed ID` when no fix exists yet.
- Never hand-edit lockfiles.

## 1. Audit

```bash
bun audit [--audit-level=high] [--json]     # per workspace root
uv audit [--no-dev] [--output-format json]  # --all-groups if tooling matters
```

Both exit non-zero on findings. Note per finding: package, version, advisory id, severity, fixed-in, direct or
transitive (`bun why X`, `uv tree --invert --package X`).

## 2. Fix

```bash
bun audit fix --dry-run      # then without --dry-run: lowest safe version within existing ranges
bun audit fix --latest       # only for what remains; rewrites package.json, treat as a major bump
uv lock --upgrade-package <pkg> && uv sync
```

- uv, range excludes the fix: widen that specifier (`uv add "pkg>=<fixed>"`), re-lock.
- Transitive: upgrade the direct dependency pulling it in. Upstream not fixed yet: say so, don't force a constraint.
- No fix exists: check reachability, consider an alternative, `bdt issue create --title "..."` (advisory, impact),
  then `--ignore-until-fixed` (uv) / `--ignore` (bun) with the link.

## 3. Verify

Re-run the audit: finding gone, no new ones. Run type check and relevant tests. Separate commits for Python and JS,
one per major bump. Already clean: say so, no commit.

## 4. PR

Per finding: advisory id, severity, old → new, how fixed; for open ones the reason and issue link.
