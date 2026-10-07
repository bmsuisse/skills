# maintenance: audit

Rule for this mode: see "never lock" in [SKILL.md](../SKILL.md).

```bash
bun audit [--audit-level=high] [--json]       # per workspace root
uv audit [--no-dev] [--output-format json]    # dev group included by default; other groups: --only-group <g>; needs network
```

Both exit non-zero on findings. Note per finding: package, version, advisory id, severity, fixed-in, direct or
transitive (`bun why X`, `uv tree --invert --package X`). Fix:

```bash
bun audit fix --dry-run                 # then for real: lowest safe version within existing ranges
bun audit fix --latest                  # only for what remains; rewrites package.json, treat as a major bump
uv lock --upgrade-package <pkg> && uv sync
```

- uv, range excludes the fix: widen that specifier (`uv add "pkg>=<fixed>"`), re-lock.
- Transitive: upgrade the direct dependency pulling it in. Upstream unfixed: say so, don't force a constraint.
- Ignoring is not fixing: only if the code path is unreachable, with reason and issue link in the PR.
  Prefer `uv audit --ignore-until-fixed ID` when no fix exists yet.
- Re-run the audit: finding gone, no new ones. Already clean: say so, no commit.
