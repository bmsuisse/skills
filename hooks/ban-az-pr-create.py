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

ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1")
WRAPPERS = {"nohup", "setsid", "time", "command", "exec", "env", "sudo", "timeout", "xargs", "builtin"}
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"}
SHELL_PUNCT = set(";&|()\n")


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies so their lines are not parsed as shell commands."""
    out: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in command.split("\n"):
        if pending:
            delim, dash = pending[0]
            if (line.strip() if dash else line) == delim:
                pending.pop(0)
            continue
        out.append(line)
        pending = [(m.group(2), "<<-" in m.group(0)) for m in HEREDOC.finditer(line)]
    return "\n".join(out)


def split_simple_commands(command: str) -> list[list[str]]:
    """Split a command line into simple commands, respecting quotes and line continuations."""
    command = strip_heredocs(command.replace("\\\n", ""))
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    out: list[list[str]] = [[]]
    for tok in tokens:
        if tok and set(tok) <= SHELL_PUNCT:
            out.append([])
        else:
            out[-1].append(tok)
    return out


def is_az_pr_create(command: str) -> bool:
    for tokens in split_simple_commands(command):
        while tokens and (ASSIGNMENT.match(tokens[0]) or tokens[0] in KEYWORDS):
            tokens = tokens[1:]
        if not tokens:
            continue
        if tokens[0] in WRAPPERS:
            # wrapper options may take values (`env -u VAR`, `timeout 5`), so look for az anywhere after it
            tokens = tokens[next((i for i, t in enumerate(tokens) if t == "az"), len(tokens)) :]
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
