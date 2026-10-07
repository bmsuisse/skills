# maintenance: bump

Rule for this mode: see "never lock" in [SKILL.md](../SKILL.md).

```bash
uv tree --outdated --depth 1 --all-groups
uv lock --upgrade && uv sync            # then raise lower bounds: uv add [--group <g>] "pkg>=X.Y"
uvx prek autoupdate                     # if the repo uses prek

bun outdated                            # -r in workspaces
bun update                              # within ranges: commit
bun update --latest <pkg>               # majors: one package/ecosystem per commit, no blanket --latest
```

`uv add` without `--group` moves a dev dependency into runtime deps: always pass the group it lives in.
Keep the existing specifier style (`>=`, caret). A Python major excluded by the range: widen that one specifier,
own commit. Read the changelog before every major. Per step: type check, lint, relevant tests
(`uv run ty check`, `bun run tsc --noEmit`), `bun run build` for frontend majors. Breakage: fix to the new API;
too big or upstream regression: see the rule above. A stray `package-lock.json`/`yarn.lock` next to `bun.lock`: flag it.
