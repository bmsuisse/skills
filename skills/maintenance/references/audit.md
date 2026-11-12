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

## Fixes younger than the cooldown

A fix newer than the [cooldown](bump.md#cooldown) is blocked (`bun audit fix` "blocked", `uv lock` keeps the old
version). It is exempted from the cooldown only through this flow, never by editing the config.

`bdt deps advisories [--path DIR ...]` (OSV; PyPI and npm only, other sources are listed as unsupported) reports per
locked package one status:

| Status | Meaning | Action |
|---|---|---|
| `exempt-eligible` | the locked version is affected, a compatible fixed version exists, and the advisory is high/critical or in CISA KEV | apply the exception below |
| `informational` | affected, but lower severity | wait out the cooldown |
| `needs-triage` | severity, affected range or fix is missing, conflicting or unparseable | a human decides, no exception |
| `blocked` | no fixed version compatible with the declared constraints | issue, see the rules above |

If OSV or the KEV feed can't be read, the command exits non-zero: an incomplete answer is never "clean". A `MAL-`
advisory on a locked version is not a bump: use [incident.md](incident.md).

Exception, **per invocation**, one package, the lowest compatible fixed version the report names (never "latest"),
nothing committed to the manifest:

```bash
uv lock --upgrade-package X --exclude-newer-package X=false && uv lock    # the plain lock drops the override again
uv lock --check                                                            # and X is at the fixed version, no X under [options.exclude-newer-package]

# bun >= 1.4.4: add "X@<fixed>" to minimumReleaseAgeExcludes in bunfig.toml (older bun: the bare name), then
bun update X
git checkout bunfig.toml                                                   # back to the committed config
```

The PR lists every exception (advisory, severity, KEV, fixed version, release age) and what stayed informational.
An advisory proves the *old* version bad, not the new one good: a hijacked "fix" release is the residual risk, so the
reviewer looks at the new release (changelog, publisher, provenance) and the PR is never merged by the agent. Being
eligible to skip the cooldown is not being safe to merge: the normal checks apply.
