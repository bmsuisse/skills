#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): regenerate the locale JSON after `translations.toml` is edited.

`translations.toml` is the source of truth; `frontend/src/locales/*.json` are git-ignored build
artifacts. Runs the project's shared `just translate` recipe (CCMT2, OneSales and MDMApp all use that
name), so the hook never needs to know where the files go: that lives in `[tool.bdt.translate]`.

Exit 2 with the output on stderr when the recipe fails (e.g. `t("KEY")` used in code but missing from
the toml), which Claude Code hands to the model. A no-op (exit 0) for any other file, or when `just`
or a `translate` recipe is missing: it never blocks unrelated work.

Runs under the system `python3` (maybe 3.12), so it avoids syntax newer than that, e.g. unparenthesized
`except A, B:`, which a py314-targeted `ruff format` would otherwise produce from `except (A, B):`.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

RECIPE = "translate"


def find_justfile_dir(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if any((d / n).is_file() for n in ("justfile", "Justfile", ".justfile")):
            return d
    return None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 1, f"`{' '.join(cmd)}` timed out after 120s"
    return p.returncode, (p.stdout + p.stderr).strip()


def translate(file: Path) -> str:
    just = shutil.which("just")
    root = find_justfile_dir(file.parent)
    if not just or not root:
        return ""
    if run([just, "--show", RECIPE], root)[0] != 0:  # no `translate` recipe in this project
        return ""
    code, out = run([just, RECIPE], root)
    return out if code != 0 else ""


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    raw = data.get("tool_input", {}).get("file_path", "") if isinstance(data, dict) else ""
    file = Path(raw).resolve() if raw else None
    if not file or file.name != "translations.toml" or not file.is_file():
        return 0
    try:
        problems = translate(file)
    except OSError:
        return 0  # a missing or non-executable `just` must not block editing
    if problems:
        print(f"`just {RECIPE}` failed after editing {file.name}. Fix it and rerun:\n{problems}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
