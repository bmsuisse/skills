#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: blocks Edit/Write/NotebookEdit outside a worktree or .claude dir.

Enforces dev-workflow's "Worktree" step: real code changes should land inside a
git worktree (or, on VCS-agnostic setups, a directory whose name starts with
`worktree`/`.worktree`), never directly in a shared main checkout. Edits under a
`.claude/` directory are always allowed, since that's where the worktree itself
(`.claude/worktrees/...`) and session-local config live.
"""

import json
import re
import sys

ALLOWED_PATH = re.compile(r"(^|/)(\.?worktree[^/]*|\.claude)(/|$)")


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
                "systemMessage": reason,
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
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not path:
        return

    if ALLOWED_PATH.search(path):
        return

    deny(f"Blocked: edits are only allowed inside a worktree*/.worktree*/.claude directory (path: {path})")


if __name__ == "__main__":
    main()
