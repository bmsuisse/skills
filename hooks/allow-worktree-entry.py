#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: auto-approves EnterWorktree for worktree-shaped targets.

Complements require-worktree-edits.py's enforcement that real edits happen inside
a worktree: this hook removes the matching friction on the other side by
auto-allowing EnterWorktree whenever the target `path` (switching into an
existing worktree) or `name` (creating a new one) looks like a worktree - i.e.
contains a `worktree*`/`.worktree*` path segment, same convention used
throughout this repo. Anything else falls through to the normal permission
flow unchanged.
"""

import json
import re
import sys

WORKTREE_SEGMENT = re.compile(r"(^|/)\.?worktree[^/]*(/|$)")


def allow(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = data.get("tool_input", {})
    target = tool_input.get("path") or tool_input.get("name") or ""
    if not target:
        return

    if WORKTREE_SEGMENT.search(target):
        allow(f"worktree dir matches worktree*/.worktree* pattern (target: {target})")


if __name__ == "__main__":
    main()
