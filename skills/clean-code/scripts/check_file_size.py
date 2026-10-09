#!/usr/bin/env python3
"""Fail when source files are too long (pre-commit / CI gate). Usage: check_file_size.py FILE...

Limits are per extension, tests get 1.5x, lock files and generated code are skipped. Files above
WARN_RATIO of their limit (but under it) only warn, so growth is visible before it blocks.
Edit LIMITS per repo. Limits are a backstop: split by reason to change, not to hit the number.
"""

import sys
from pathlib import Path

LIMITS = {".py": 1200, ".ts": 600, ".tsx": 900, ".vue": 900, ".sql": 1200, ".sh": 100, ".md": 500}
WARN_RATIO = 0.75
TEST_FACTOR = 1.5


def relative(path: Path) -> Path:
    """Path relative to the cwd, so a parent dir named 'generated' (or absolute CI paths) can't skew checks."""
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path


def is_skipped(path: Path) -> bool:
    rel = relative(path)
    return (
        path.suffix == ".lock"
        or path.name.endswith(".lock.json")
        or ".generated." in path.name
        or ".gen." in path.name
        or "generated" in rel.parts
    )


def is_test(path: Path) -> bool:
    name, parts = path.name, relative(path).parts
    return (
        name.startswith(("test_", "tests_"))
        or name == "conftest.py"
        or Path(name).stem.endswith("_test")
        or ".test." in name
        or ".spec." in name
        or "tests" in parts
        or "__tests__" in parts
    )


def limit_for(path: Path) -> int | None:
    limit = LIMITS.get(path.suffix)
    return int(limit * TEST_FACTOR) if limit and is_test(path) else limit


def main(files: list[str]) -> int:
    failed = False
    for name in files:
        path = Path(name)
        if not path.is_file() or is_skipped(path) or (limit := limit_for(path)) is None:
            continue
        try:
            lines = len(path.read_text(encoding="utf-8").splitlines())
        except (UnicodeDecodeError, OSError) as e:
            print(f"Warning: {name} not checked ({type(e).__name__})")  # visible, but never a stack trace
            continue
        if lines > limit:
            failed = True
            print(f"Error: {name} is too long ({lines} lines, limit {limit}). Split by reason to change.")
        elif lines > limit * WARN_RATIO:
            print(f"Warning: {name} has {lines} lines (limit {limit}). Consider splitting before it blocks.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
