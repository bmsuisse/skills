#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write|MultiEdit, Codex apply_patch): regenerate the locale JSON after `translations.toml` is edited.

`translations.toml` is the source of truth; the generated `<lng>.json` files are git-ignored build
artifacts. Runs `uv run bdt translate` in the nearest parent of the edited file whose `pyproject.toml`
has `[tool.bdt.translate]` (so an edit inside a git worktree regenerates that worktree, not the main
checkout); where the files go lives in that config. Only files inside `$CLAUDE_PROJECT_DIR` (the cwd when
unset) are handled.

Exit 2 with the output on stderr when `bdt translate` fails (e.g. `t("KEY")` used in code but missing from
the toml), which the agent sees. A no-op (exit 0) for any other file, or when `uv` or the config is missing:
it never blocks unrelated work.

Runs under the system `python3` (maybe 3.12), so it avoids syntax newer than that, e.g. unparenthesized
`except A, B:`, which a py314-targeted `ruff format` would otherwise produce from `except (A, B):`.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_MARKER = "[tool.bdt.translate]"
TARGET = "translations.toml"
# Codex edits files with apply_patch: tool_input.command holds the patch, whose headers name the files it touches.
PATCH_FILE_HEADER = re.compile(r"^\*\*\* (?:Add File|Update File|Move to): (.+?)\s*$", re.MULTILINE)


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()


def is_configured(directory: Path) -> bool:
    pyproject = directory / "pyproject.toml"
    return pyproject.is_file() and CONFIG_MARKER in pyproject.read_text(errors="ignore")


def owning_root(file: Path, project: Path) -> Path | None:
    """Nearest directory from the file up to (and including) the project that configures `bdt translate`."""
    if not file.is_relative_to(project):
        return None
    for d in file.parents:
        if is_configured(d):
            return d
        if d == project:
            break
    return None


def edited_files(data: dict) -> list[Path]:
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    paths = [tool_input.get("file_path")]
    if isinstance(tool_input.get("command"), str):
        paths += PATCH_FILE_HEADER.findall(tool_input["command"])
    base = Path(data.get("cwd") or os.getcwd())
    return [(base / p).resolve() for p in paths if isinstance(p, str) and p and Path(p).name == TARGET]


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 1, f"`{' '.join(cmd)}` timed out after 120s"
    return p.returncode, (p.stdout + p.stderr).strip()


def translate(files: list[Path]) -> str:
    uv = shutil.which("uv")
    if not uv:
        return ""
    project = project_dir()
    roots = {r for f in files if f.is_file() and (r := owning_root(f, project))}
    problems = []
    for root in sorted(roots):
        code, out = run([uv, "run", "bdt", "translate"], root)
        if code != 0:
            problems.append(out)
    return "\n".join(problems)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    files = edited_files(data) if isinstance(data, dict) else []
    if not files:
        return 0
    try:
        problems = translate(files)
    except OSError:
        return 0  # a missing or non-executable `uv` must not block editing
    if problems:
        print(f"`uv run bdt translate` failed after editing {TARGET}. Fix it and rerun:\n{problems}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
