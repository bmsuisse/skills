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
"""

import glob
import json
import os
import re
import sys

PUBLISH_PATTERNS = [
    re.compile(r"\bbdt\s+pr\s+publish\b"),
    re.compile(r"\bbdt\s+pr\s+create\b[^\n]*--no-draft\b"),
    re.compile(r"\baz\s+repos\s+pr\s+(create|update)\b[^\n]*--auto-complete\b(\s+true)?"),
    re.compile(r"\baz\s+repos\s+pr\s+update\b[^\n]*--draft\s+false\b"),
    re.compile(r"\baz\s+repos\s+pr\s+update\b[^\n]*--status\s+completed\b"),
    re.compile(r"\bgh\s+pr\s+create\b(?![^\n]*--draft\b)"),
    re.compile(r"\bgh\s+pr\s+ready\b(?![^\n]*--undo\b)"),
    re.compile(r"\bgh\s+pr\s+merge\b"),
]

CODE_REVIEW_SKILL = re.compile(r'"skill"\s*:\s*"code-review(:[^"]*)?"')


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
    if not any(p.search(command) for p in PUBLISH_PATTERNS):
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
