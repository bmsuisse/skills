# maintenance: lint

Keeps a Python project on the ruff/ty baseline that `init-app-stack` scaffolds. Rule for the version bumps: see "never lock" in
[SKILL.md](../SKILL.md). Source of truth: the `[tool.ruff*]` block in
`init-app-stack`'s `scripts/create.py` and the `prek` skill's ruff section (`skills/init-app-stack/`, `skills/prek/` in
bmsuisse/skills); read them, don't copy the config from here, so it can't go stale.

**Run per `pyproject.toml` that has Python code** (see [bump.md](bump.md) for finding projects). Do `bump` first.

1. **Dev deps present and latest**: `ruff` and `ty` in the dev group (`uv tree --outdated --depth 1 --all-groups`).
   Missing: `uv add --dev ruff ty`. Behind: `uv lock --upgrade-package ruff --upgrade-package ty`, raise the specifier
   (`uv add --group dev "ruff>=X.Y"`). `uvx` or a global install doesn't count, CI must run the pinned-by-lock version.
2. **`[tool.ruff]` matches the baseline**: `line-length`, `target-version` (= project `requires-python`), `extend-exclude = ["*.md"]`
   (ruff 0.16 lints Markdown code blocks), and an explicit `[tool.ruff.lint] select` that includes every family of the
   baseline (diff the project's list against `create.py`'s). Missing families are added, existing extras stay.
   `ignore` may keep `ANN401` only if the `ruff-warn-any` prek hook exists; banned imports and `ban-relative-imports` as in the baseline.
   Intentional project exceptions (`per-file-ignores`) stay, mention new ones in the PR.
3. **`prek.toml`** (if used): `ruff-pre-commit` `rev` equals the lock's ruff version; `ty` runs (hook or CI).
4. **Run both**: `uv run ruff format`, `uv run ruff check --fix`, `uv run ty check`. Adding newly selected families to an
   old codebase can flag hundreds of lines: autofix in its own commit, fix the rest per family, one commit each. Fix
   violations, don't `# noqa` or `ty: ignore` them; a rule that truly doesn't fit goes out of `select` deliberately, with the reason in the PR.
   Too big to finish: leave that family out of `select`, `bdt issue create --title "..."`, link it in the PR.
5. Already on the baseline and clean: say so, no commit. `bdt lint` checks that ruff, ty, pytest and prek are declared.

Don't touch `[tool.ruff]` in non-Python repos and don't add ruff/ty to a project that has no `pyproject.toml`.
