#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: blocks PR-publish commands until /code-review has run this session.

Reads the hook's stdin JSON (tool_name, tool_input, transcript_path), and for Bash
commands that publish/complete/un-draft a PR:

  bdt pr publish                                 (marks a draft PR ready for review)
  bdt pr create --no-draft                       (bdt >=0.12 defaults `pr create` to
                                                   draft; --no-draft opts out)
  az repos pr create/update --auto-complete       (Azure DevOps)
  az repos pr update --draft false
  az repos pr update --status completed
  gh pr create        (without --draft)          (GitHub CLI)
  gh pr ready          (without --undo)
  gh pr merge

...it checks the session transcript - plus any subagent transcripts under
<session-dir>/subagents/ - for a prior Skill(code-review) invocation (matching
dev-workflow's "Review. Run /code-review on the diff" step). A subagent that ran
/code-review on the caller's behalf satisfies the gate too. Denies if no such
invocation is found anywhere in the session.

Matching is done on shell-tokenized words (via shlex), not a raw substring/regex
search over the whole command string. This means a phrase like "bdt pr publish"
sitting inside a quoted --description, commit message, or grep pattern is a single
token and does not look like an actual invocation - only real, unquoted, adjacent
command words trigger the gate.
"""

import glob
import json
import os
import re
import shlex
import sys

CODE_REVIEW_SKILL = re.compile(r'"skill"\s*:\s*"code-review(:[^"]*)?"')


def tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        # Unbalanced quotes etc. - fall back to a naive split so we still see something.
        return command.split()


def has_subsequence(tokens: list[str], seq: list[str]) -> bool:
    n = len(seq)
    return any(tokens[i : i + n] == seq for i in range(len(tokens) - n + 1))


def token_after(tokens: list[str], target: str) -> str | None:
    try:
        i = tokens.index(target)
    except ValueError:
        return None
    return tokens[i + 1] if i + 1 < len(tokens) else None


def is_pr_publish_command(tokens: list[str]) -> bool:
    if has_subsequence(tokens, ["bdt", "pr", "publish"]):
        return True
    if has_subsequence(tokens, ["bdt", "pr", "create"]) and "--no-draft" in tokens:
        return True

    is_az_pr_create_or_update = has_subsequence(tokens, ["az", "repos", "pr", "create"]) or has_subsequence(
        tokens, ["az", "repos", "pr", "update"]
    )
    if is_az_pr_create_or_update and "--auto-complete" in tokens and token_after(tokens, "--auto-complete") != "false":
        return True

    if has_subsequence(tokens, ["az", "repos", "pr", "update"]):
        if token_after(tokens, "--draft") == "false":
            return True
        if token_after(tokens, "--status") == "completed":
            return True

    if has_subsequence(tokens, ["gh", "pr", "create"]) and "--draft" not in tokens:
        return True
    if has_subsequence(tokens, ["gh", "pr", "ready"]) and "--undo" not in tokens:
        return True
    if has_subsequence(tokens, ["gh", "pr", "merge"]):
        return True

    return False


def code_review_ran(transcript_path: str) -> bool:
    if not transcript_path or not os.path.exists(transcript_path):
        return False

    files = [transcript_path]
    if transcript_path.endswith(".jsonl"):
        session_dir = transcript_path[: -len(".jsonl")]
        files += glob.glob(os.path.join(session_dir, "subagents", "*.jsonl"))

    for path in files:
        try:
            with open(path, "r", errors="ignore") as fh:
                for line in fh:
                    if CODE_REVIEW_SKILL.search(line):
                        return True
        except OSError:
            continue
    return False


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

    if data.get("tool_name") != "Bash":
        return

    command = data.get("tool_input", {}).get("command", "")
    if not is_pr_publish_command(tokenize(command)):
        return

    if code_review_ran(data.get("transcript_path", "")):
        return

    deny(
        "Blocked: this command publishes/completes a PR, but /code-review has not "
        "been run yet in this session (directly or via a subagent). Run /code-review "
        "first, then retry."
    )


if __name__ == "__main__":
    main()
