#!/usr/bin/env python3
"""Auto-generates the Available Skills table in README.md from skills/ frontmatter."""

import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "skills"
README = Path(__file__).parent.parent / "README.md"

START_MARKER = "<!-- SKILLS_TABLE_START -->"
END_MARKER = "<!-- SKILLS_TABLE_END -->"


def parse_frontmatter(skill_md: Path) -> dict[str, str]:
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm: dict[str, str] = {}
    lines = match.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # Handle YAML block scalars: > (folded) and | (literal)
            if value in (">", "|"):
                block_lines = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or lines[i] == ""):
                    block_lines.append(lines[i].strip())
                    i += 1
                fm[key] = " ".join(filter(None, block_lines))
                continue
            fm[key] = value
        i += 1
    return fm


def build_table() -> str:
    rows: list[tuple[str, str]] = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue
        fm = parse_frontmatter(skill_md)
        name = fm.get("name", skill_dir.name)
        description = fm.get("description", "")
        if len(description) > 120:
            description = description[:117].rstrip() + "…"
        rows.append((name, description))

    lines = [
        "| Skill | Description |",
        "|---|---|",
    ]
    for name, description in rows:
        lines.append(f"| [{name}](./skills/{name}/) | {description} |")
    return "\n".join(lines)


def update_readme() -> None:
    content = README.read_text(encoding="utf-8")
    table = build_table()
    replacement = f"{START_MARKER}\n{table}\n{END_MARKER}"
    pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
    new_content, n = re.subn(pattern, replacement, content, flags=re.DOTALL)
    if n == 0:
        print("ERROR: markers not found in README.md", file=sys.stderr)
        sys.exit(1)
    README.write_text(new_content, encoding="utf-8")
    print(f"Updated README.md with {len(table.splitlines()) - 2} skill(s).")


if __name__ == "__main__":
    update_readme()
