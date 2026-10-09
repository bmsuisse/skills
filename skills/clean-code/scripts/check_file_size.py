#!/usr/bin/env python3
"""Fail when source files are too long (pre-commit / CI gate). Usage: check_file_size.py FILE...

Limits are per extension, tests get 1.5x, lock files and generated code are skipped. Files
above WARN_LINES (but under the limit) only warn, so the team sees growth before it blocks.
Override limits per repo by editing LIMITS; nothing here is language-specific beyond that table.
"""

import sys
from pathlib import Path

LIMITS = {".py": 1200, ".ts": 600, ".tsx": 900, ".vue": 900, ".sql": 1200, ".sh": 100, ".md": 500}
WARN_LINES = 600
TEST_FACTOR = 1.5


def is_skipped(path: Path) -> bool:
    return (
        path.suffix == ".lock"
        or path.name.endswith(".lock.json")
        or ".generated." in path.name
        or ".gen." in path.name
        or "generated" in path.parts
    )


def limit_for(path: Path) -> int | None:
    limit = LIMITS.get(path.suffix)
    is_test = path.name.startswith("test_") or ".test." in path.name or ".spec." in path.name
    return int(limit * TEST_FACTOR) if limit and is_test else limit


def main(files: list[str]) -> int:
    failed = False
    for name in files:
        path = Path(name)
        if not path.is_file() or is_skipped(path) or (limit := limit_for(path)) is None:
            continue
        try:
            lines = len(path.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            continue  # binary or unknown encoding
        if lines > limit:
            failed = True
            print(f"Error: {name} is too long ({lines} lines, limit {limit}). Split by reason to change.")
        elif lines > WARN_LINES:
            print(f"Warning: {name} has {lines} lines (> {WARN_LINES}). Consider splitting before it blocks.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
