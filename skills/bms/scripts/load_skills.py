#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
Load and concatenate bmsuisse skill files for a given bms mode.

Reads SKILL.md files from the skills directory and prints combined content.
Claude runs this script to load all relevant skills in one step instead of
reading each file individually.

Usage:
  uv run skills/bms/scripts/load_skills.py [base|sql|python|data]
  uv run skills/bms/scripts/load_skills.py           # defaults to base
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILLS_ROOT = Path(__file__).parent.parent.parent  # skills/

MODES: dict[str, list[str]] = {
    "base": [
        "coding-guidelines-sql",
        "coding-guidelines-python",
        "coding-guidelines-typescript",
        "fabricks-glossary",
    ],
    "sql": [
        "coding-guidelines-sql",
        "sql-optimization",
        "fabricks-glossary",
    ],
    "python": [
        "coding-guidelines-python",
    ],
    "data": [
        "data-modeling-dimensional",
        "fabricks-glossary",
    ],
}


def load_mode(mode: str) -> str:
    skills = MODES.get(mode)
    if skills is None:
        valid = ", ".join(MODES)
        raise SystemExit(f"Unknown mode '{mode}'. Valid: {valid}")

    parts: list[str] = []
    missing: list[str] = []

    for skill_name in skills:
        skill_file = SKILLS_ROOT / skill_name / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8")
            parts.append(f"# === {skill_name} ===\n\n{content}")
        else:
            missing.append(skill_name)

    if missing:
        print(f"Warning: skill file(s) not found: {', '.join(missing)}", file=sys.stderr)

    return "\n\n---\n\n".join(parts)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "base"
    print(load_mode(mode))


if __name__ == "__main__":
    main()
