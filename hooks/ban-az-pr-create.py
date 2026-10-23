#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: blocks creating PRs through the Azure CLI (`az repos pr create`).

dev-workflow opens and publishes PRs with `bdt pr create` / `bdt pr publish`, which link the issue, open the PR
as a draft and trigger the right pipelines. A PR created with `az` skips all of that, so the command is denied
with a pointer to `bdt`. Other `az repos pr` subcommands (show, list, update, ...) are unaffected.
"""

import json
import re
import shlex
import sys

SEGMENT_SPLIT = re.compile(r"&&|\|\||[;&|\n()]")
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
WRAPPERS = {"nohup", "setsid", "time", "command", "exec", "env", "sudo"}


def tokenize(segment: str) -> list[str]:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def is_az_pr_create(command: str) -> bool:
    for segment in SEGMENT_SPLIT.split(command):
        tokens = tokenize(segment)
        while tokens and (ASSIGNMENT.match(tokens[0]) or tokens[0] in WRAPPERS):
            tokens = tokens[1:]
        if tokens[:4] == ["az", "repos", "pr", "create"]:
            return True
    return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    if data.get("tool_name") != "Bash":
        return

    if not is_az_pr_create(data.get("tool_input", {}).get("command", "")):
        return

    reason = (
        "Blocked: do not create PRs with `az repos pr create`. Use `bdt pr create --target <branch> "
        "--title \"...\"` instead (opens a draft PR; extra az/gh flags go after `--`, e.g. `-- --work-items 123`), "
        "then `bdt pr publish` once reviewed. See `bdt pr create --help` and the dev-workflow skill."
    )
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


if __name__ == "__main__":
    main()
