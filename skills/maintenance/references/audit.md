# maintenance: audit

Rule for this mode: see "never lock" in [SKILL.md](../SKILL.md).

**Run per project directory** (every `uv.lock` / `bun.lock`, see [bump.md](bump.md)): a root `uv audit` misses
non-member projects like `tests_e2e/`, and bun has no workspaces in most repos. Needs network. Do `bump` first
(`bun update` unblocks fixes that `bun audit fix` reports as "blocked by range").

```bash
bun audit [--audit-level=high] [--json]
uv audit [--no-dev] [--output-format json]    # experimental (warns); audits all groups; --no-group <g> narrows
```

Both exit non-zero on findings. Note per finding: package, version, advisory id, fixed-in, direct or transitive
(`bun why X`, `uv tree --invert --package X`). Severity: bun reports it; `uv audit` doesn't, use the advisory link.
uv lists a GHSA and its PYSEC alias as two findings: count them once. With dozens of findings, summarize per package, not per advisory.

```bash
bun audit fix --dry-run                 # check it for downgrades; then for real. Bumps exact pins: that is the fix, list them in the PR
bun audit fix --latest                  # only for what remains; rewrites package.json, treat as a major bump, never apply a downgrade
uv lock --upgrade-package <pkg> && uv sync
```

- bun "blocked by a dependent's range": bump the parent (all `@tiptap/*` together, `@hey-api/*`, `mermaid`...), then re-run.
  "No published version fixes": issue, then `bun audit fix --ignore GHSA-...` with the link.
- `uv lock --upgrade-package` can cross majors (check the lock diff, e.g. cryptography, oauthlib).
- uv, range excludes the fix: widen that specifier (`uv add [--group <g>] "pkg>=<fixed>"`), re-lock.
- **A cap/constraint blocks the fix** (`constraint-dependencies = ["cryptography<44"]`, `setuptools<75`,
  `pytest<9`): lifting it is the fix, even though it was a pin. Say which and why in the PR.
- Transitive: upgrade the direct dependency pulling it in. Held by an upstream range (e.g. a connector capping
  `oauthlib<4`): say so, open an issue, don't force a constraint.
- Fix published outside the registry (e.g. `xlsx`/SheetJS ships fixes from its own CDN) or no fix at all: issue,
  and consider an alternative package.
- Ignoring is not fixing: only if the code path is unreachable, with reason and issue link in the PR.
  `uv audit --ignore-until-fixed ID` / `--ignore ID`; bun: `bun audit --ignore GHSA-...`, `bun audit fix --ignore GHSA-...`.
- Re-run the audit: finding gone, no new ones. Already clean: say so, no commit.
