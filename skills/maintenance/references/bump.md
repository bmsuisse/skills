# maintenance: bump

Rule for this mode: see "never lock" in [SKILL.md](../SKILL.md).

**Run per project directory**: every `uv.lock` / `bun.lock`
(`find . \( -name uv.lock -o -name bun.lock \) -not -path '*/node_modules/*' -not -path './.*'`). Nested projects
(`tests_e2e/`) and separate frontends are not covered by a root command; bun often has no workspaces, so `-r` doesn't help.

```bash
uv tree --outdated --depth 1 --all-groups
uv lock --upgrade && uv sync            # then raise lower bounds: uv add [--group <g>] "pkg>=X.Y"
uvx prek autoupdate                     # if the repo uses prek

bun outdated
bun update                              # within ranges: commit
bun update --latest <pkg>               # majors: one package/ecosystem per commit, no blanket --latest
```

- **`uv lock --upgrade` crosses majors** for open `>=` specifiers. Afterwards list the major jumps from the
  `uv.lock` diff (`git diff uv.lock`) and review/commit each separately (re-lock them with `--upgrade-package`); revert one that breaks and see "If it breaks".
- `uv add` without `--group` moves a dev dependency into runtime deps: always pass the group it lives in.
  Across several pyprojects script it, don't hand-edit each.
- Keep the existing specifier style (`>=`, caret). A Python major excluded by the range: widen that one specifier,
  own commit. Read the changelog before every major.
- **Existing caps (`<`, `~=`, `constraint-dependencies`):** leave them, but list each in the PR with the latest
  version it blocks, so a human can decide.
- **Stale exact pins** (`bun update` and `uv lock --upgrade` leave them): list the ones behind latest in the PR
  (`bun outdated`, where Update ≠ Current).
- `prek autoupdate` needs a git repo; keep `prek.toml`'s ruff `rev` equal to the pyproject ruff version.
- Private index (`uv lock` 401): export `UV_INDEX_<NAME>_USERNAME`/`_PASSWORD` from the repo's documented credentials.
- Per step: type check, lint, relevant tests (`uv run ty check`, `bun run tsc --noEmit`), `bun run build` for
  frontend majors.
- Stray `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` next to `bun.lock`: flag it; if it is an empty or stale
  stub, recommend deleting it.

## Cooldown

Every project resolves with a **5-day cooldown**: a release younger than that is not picked, so a hijacked or
malicious release is normally pulled before we install it (most such releases are removed within days; the window is
a policy choice, not a guarantee). It only acts when a version is *resolved* (`uv lock`, `bun update`/`add`); a version
already in the lockfile stays, and `uvx` or global installs ignore it.

```toml
# pyproject.toml (uv >= 0.9.17): a relative span, never an absolute date; uv.lock records it as `exclude-newer-span`
[tool.uv]
exclude-newer = "5 days"
exclude-newer-package = { bmsdna-devtools = false }   # our own packages, listed by name (no wildcard)
```

```toml
# bunfig.toml next to package.json (bun >= 1.3)
[install]
minimumReleaseAge = 432000                                   # seconds
minimumReleaseAgeExcludes = ["@bmsuisse/ui", "@bmsuisse/datagrid"]   # every @bmsuisse/* package the project uses
```

- **Our own packages are exempt**: `bmsdna-devtools` and everything under `@bmsuisse/`. Neither tool takes a wildcard
  (bun 1.4.2 and 1.4.4 ignore `@bmsuisse/*`), so list each one the project depends on. They are public on PyPI/npm:
  the exemption is only safe while BMS alone controls publishing those names.
- A project without the config gets it as its own first commit, with a PR note. `uv lock --upgrade` / `bun update` then
  see only releases older than the window.
- Our private Azure DevOps feed reports upload times, so no extra config. For an index without them uv treats the
  files as unavailable: opt that index/package out, don't drop the cooldown.
- `bun update` rewrites the range in `package.json` to the resolved version; expected.
- Frozen installs in CI (`uv sync --locked`, `bun install --frozen-lockfile`): flag a pipeline that re-resolves.
- A fix younger than the cooldown: see [audit.md](audit.md#fixes-younger-than-the-cooldown), not an edit of this config.

## If it breaks

Fix to the new API; too big or an upstream regression: leave that package, don't pin, `bdt issue create --title "..."`
and link it in the PR.
