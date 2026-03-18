#!/usr/bin/env python3
"""
install-skills.py — cross-platform companion skills installer (Mac / Linux / Windows)

Usage:
    uv run python install-skills.py

Installs companion skills via `npx skills add` into:
    .agents/skills/   (Antigravity)
    .agent/skills/    (Antigravity alternate)
    .claude/skills/   (Claude Code)
"""

import subprocess
import sys

SKILLS = [
    ("https://github.com/nuxt/ui", "nuxt-ui"),
    ("https://github.com/antfu/skills", "nuxt"),
    ("https://github.com/anthropics/skills", "frontend-design"),
    ("https://github.com/wshobson/agents", "fastapi-templates"),
]


def run(cmd: list[str], label: str) -> bool:
    print(f"  → {label}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  ⚠️  Failed (exit {result.returncode}): {label}", file=sys.stderr)
        return False
    return True


def main() -> None:
    print("📥 Installing companion skills...\n")

    for repo, skill in SKILLS:
        print(f"📦 {skill}  ({repo})")
        run(
            ["npx", "skills", "add", repo, "--skill", skill],
            f"npx skills add {repo} --skill {skill}",
        )
        print()

    print("✅ All skills installed.")
    print()
    print("Skills are available in:")
    print("  .agents/skills/   (Antigravity)")
    print("  .agent/skills/    (Antigravity alternate)")
    print("  .claude/skills/   (Claude Code)")


if __name__ == "__main__":
    main()
