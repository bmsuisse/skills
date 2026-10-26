#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write|MultiEdit): regenerate the locale JSON after `translations.toml` is edited.

`translations.toml` is the source of truth; the generated `<lng>.json` files are git-ignored build
artifacts. Runs `uv run bdt translate` in the project root; where the files go lives in
`[tool.bdt.translate]`, so the hook needs no per-app configuration. Only the project at
`$CLAUDE_PROJECT_DIR` (the cwd when unset) is used, and only for files inside it.

Exit 2 with the output on stderr when `bdt translate` fails (e.g. `t("KEY")` used in code but missing from
the toml), which Claude Code hands to the model. A no-op (exit 0) for any other file, or when `uv` or the
project's `[tool.bdt.translate]` config is missing: it never blocks unrelated work.

Runs under the system `python3` (maybe 3.12), so it avoids syntax newer than that, e.g. unparenthesized
`except A, B:`, which a py314-targeted `ruff format` would otherwise produce from `except (A, B):`.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_MARKER = "[tool.bdt.translate]"


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()


def is_configured(root: Path) -> bool:
    pyproject = root / "pyproject.toml"
    return pyproject.is_file() and CONFIG_MARKER in pyproject.read_text(errors="ignore")


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 1, f"`{' '.join(cmd)}` timed out after 120s"
    return p.returncode, (p.stdout + p.stderr).strip()


def translate(file: Path) -> str:
    uv = shutil.which("uv")
    root = project_root()
    if not uv or not file.is_relative_to(root) or not is_configured(root):
        return ""
    code, out = run([uv, "run", "bdt", "translate"], root)
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
        return 0  # a missing or non-executable `uv` must not block editing
    if problems:
        print(
            f"`uv run bdt translate` failed after editing {file.name}. Fix it and rerun:\n{problems}", file=sys.stderr
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
