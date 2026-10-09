#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): lint the edited file and feed what is left back to Claude.

Python: `ruff check --fix` when the project configures ruff.
TS/JS/Vue: `biome check --write` when the project has a biome.json(c).

Auto-fixable issues are fixed silently. Anything left is printed to stderr with exit 2, which
Claude Code hands to the model so it fixes the rest now instead of at the pre-push gate.
A no-op (exit 0) when the file type, config or tool is missing: it never blocks unrelated work.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

PY = {".py"}
JS = {".ts", ".tsx", ".js", ".jsx", ".vue", ".mjs", ".cjs"}


def find_up(start: Path, names: tuple[str, ...], marker: str | None = None) -> Path | None:
    """Nearest parent directory holding one of `names` (for pyproject.toml, only if it contains `marker`)."""
    for d in [start, *start.parents]:
        for n in names:
            f = d / n
            if f.is_file() and (marker is None or n != "pyproject.toml" or marker in f.read_text(errors="ignore")):
                return d
    return None


def tool(root: Path, name: str) -> list[str] | None:
    for cand in (root / ".venv/bin" / name, root / "node_modules/.bin" / name):
        if cand.is_file():
            return [str(cand)]
    if found := shutil.which(name):
        return [found]
    return None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    return p.returncode, (p.stdout + p.stderr).strip()


def lint(file: Path) -> str:
    if file.suffix in PY:
        root = find_up(file.parent, ("ruff.toml", ".ruff.toml", "pyproject.toml"), "[tool.ruff")
        if not root:
            return ""
        ruff = tool(root, "ruff") or (["uv", "run", "--frozen", "ruff"] if shutil.which("uv") else None)
        if not ruff:
            return ""
        code, out = run([*ruff, "check", "--fix", "--force-exclude", "--output-format", "concise", str(file)], root)
        return out if code == 1 else ""  # 1 = violations; 2 = ruff/config error, which must not block edits
    if file.suffix in JS:
        root = find_up(file.parent, ("biome.json", "biome.jsonc"))
        biome = root and tool(root, "biome")
        if not biome:
            return ""
        code, out = run([*biome, "check", "--write", "--colors=off", "--no-errors-on-unmatched", str(file)], root)
        return out if code == 1 else ""
    return ""


def main() -> int:
    try:
        raw = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    except (json.JSONDecodeError, AttributeError):
        return 0
    file = Path(raw).resolve() if raw else None  # resolve: subprocesses run from the project root, not our cwd
    if not file or not file.is_file():
        return 0
    try:
        problems = lint(file)
    except (OSError, ValueError, subprocess.TimeoutExpired):  # ValueError: unreadable/non-UTF-8 config
        return 0  # ponytail: a broken or slow linter must not block editing
    if problems:
        print(f"Lint errors remain in {file.name}. Fix them (targeted `# noqa: CODE  # reason` only if justified):\n{problems}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
