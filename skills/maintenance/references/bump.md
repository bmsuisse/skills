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

## If it breaks

Fix to the new API; too big or an upstream regression: leave that package, don't pin, `bdt issue create --title "..."`
and link it in the PR.
