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
(`.claude/worktrees/...`) and session-local config live. Edits under `/tmp` or a
Windows/WSL temp directory (`AppData\\Local\\Temp`, `\\Windows\\Temp`, and their
`/mnt/<drive>/...` WSL-mounted equivalents) are also allowed, since that's where
scratchpad files and temporary worktrees live.

The gate itself is also skipped entirely when the directory containing the
edited file isn't inside a git repository, or is inside one with no remote
configured - in both cases there's no shared checkout to protect and no
remote to push a worktree branch to. This is resolved from the target path,
not the hook process's cwd, since a session's cwd can differ from the
repository actually being edited.
"""

import json
import os
import re
import subprocess
import sys

ALLOWED_PATH = re.compile(r"(^|/)(\.?worktree[^/]*|\.claude)(/|$)")
ALLOWED_PREFIX = re.compile(r"^/tmp(/|$)")
ALLOWED_WINDOWS_TEMP = re.compile(r"(?i)^([a-z]:|/mnt/[a-z])/(.*/)?(appdata/local/temp|windows/temp)(/|$)")
NOT_A_REPO = re.compile(r"not a git repository", re.IGNORECASE)


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


def _run_git(directory: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", directory, *args],
        capture_output=True,
        text=True,
        timeout=5,
    )


def _nearest_existing_dir(path: str) -> str:
    directory = os.path.dirname(os.path.abspath(path)) or os.sep
    while not os.path.isdir(directory):
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return directory


def path_exempt_from_gate(path: str) -> bool:
    """True when the edited path's repo isn't git, or is git with no remote.

    Fails closed (returns False, i.e. the gate still applies) on any git
    invocation error that isn't unambiguously "not a git repository", so a
    permission error or corrupted .git doesn't silently bypass the guardrail.
    """
    directory = _nearest_existing_dir(path)

    try:
        result = _run_git(directory, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return bool(NOT_A_REPO.search(result.stderr))
    if result.stdout.strip() != "true":
        return False

    try:
        remotes = _run_git(directory, "remote")
    except (OSError, subprocess.TimeoutExpired):
        return False
    if remotes.returncode != 0:
        return False
    return not remotes.stdout.strip()


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = data.get("tool_input", {})
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not path:
        return

    normalized = path.replace("\\", "/")
    if ALLOWED_PATH.search(normalized) or ALLOWED_PREFIX.search(normalized) or ALLOWED_WINDOWS_TEMP.search(normalized):
        return

    if path_exempt_from_gate(path):
        return

    deny(f"Blocked: edits are only allowed inside a worktree*/.worktree*/.claude directory, or /tmp (path: {path})")


if __name__ == "__main__":
    main()
