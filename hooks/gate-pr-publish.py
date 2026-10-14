#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: blocks PR-publish commands until a code review has run this session: /code-review,
/bms-code-review, or a review done by the local OpenAI `codex` CLI (see below).

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
<session-dir>/subagents/ - for a prior Skill(code-review) or Skill(bms-code-review) invocation (matching
dev-workflow's "Review. Run /code-review on the diff" step). A subagent that ran
/code-review (or /bms-code-review) on the caller's behalf satisfies the gate too. Denies if no such
invocation is found anywhere in the session.

A review done by a different agent, the `codex` CLI, counts as well, but only when the transcript holds an
actual Bash tool call that runs one of

  codex exec "<prompt that mentions a code review / the bms-code-review skill>"   (also `codex e`)
  codex review ...                                                                   (also `codex exec review`)

AND that review is known to have finished (a mere start proves nothing):

  - run in the foreground: the Bash tool_result is not an error (codex exits non-zero on failure);
  - started with run_in_background: a later <task-notification> for that tool call says "completed";
  - started in the background of the shell (`nohup codex exec ... &`; the tool_result only says "started"):
    the `-o <file>` output file exists, is non-empty and is newer than the call (codex writes it when the
    review is done). Without `-o` such a run cannot be proven finished and does not count.

The command is parsed with shlex into simple commands, so `codex` must be the command word: `codex --version`,
`codex exec --help`, `git commit -m "codex exec code review"`, `echo`, `grep` etc. never count. Like the
Claude-side check, a review counts for the whole session; it is not tied to HEAD or invalidated by later commits.

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
from dataclasses import dataclass
from datetime import datetime

# Accepts the built-in /code-review and BMS's /bms-code-review, optionally plugin-prefixed
# ("plugin:code-review").
CODE_REVIEW_SKILL = re.compile(r'"skill"\s*:\s*"(?:[^"]*:)?(?:bms-)?code-review(?::[^"]*)?"')


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


# --- review through the codex CLI -----------------------------------------------------------------------------

# A `codex exec` prompt only counts when it asks for a code review (e.g. "Use the bms-code-review skill ...").
CODEX_REVIEW_PROMPT = re.compile(r"\bcode[ -]?review", re.IGNORECASE)
CODEX_HELP_FLAGS = {"-h", "--help", "-V", "--version"}
# codex options that take a separate value (so the value is not mistaken for the subcommand / prompt).
CODEX_VALUE_OPTS = {
    "-c", "--config", "-C", "--cd", "-m", "--model", "-s", "--sandbox", "-p", "--profile", "-i", "--image",
    "-o", "--output-last-message", "--output-schema", "-a", "--ask-for-approval", "--color", "--enable",
    "--disable", "--add-dir", "--local-provider", "--base", "--commit", "--title",
}  # fmt: skip
CODEX_OUTPUT_OPTS = {"-o", "--output-last-message"}
WRAPPER_COMMANDS = {"nohup", "setsid", "time", "command", "exec", "env", "timeout", "npx", "bunx"}
SHELLS = {"bash", "sh", "zsh"}
SHELL_PUNCT = set(";&|()\n")
TASK_NOTIFICATION = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>.*?<status>([^<]+)</status>", re.DOTALL)


@dataclass
class CodexReview:
    output_file: str | None  # expanded `-o` path, None when absent or not resolvable
    background: bool  # followed by `&`: the Bash tool_result only says "started"


def split_simple_commands(command: str) -> list[tuple[list[str], str]]:
    """Split a shell command line into (words, terminator) pairs, e.g. (["codex", "exec", ...], "&")."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    out: list[tuple[list[str], str]] = []
    words: list[str] = []
    skip_next = False
    for i, tok in enumerate(tokens):
        if skip_next:  # target of a redirection (`> log`, `>&`, `<<`, ...)
            skip_next = False
        elif tok and set(tok) <= SHELL_PUNCT:
            out.append((words, tok.replace("\n", "").replace("(", "").replace(")", "")))
            words = []
        elif "<" in tok or ">" in tok:
            skip_next = True
        elif tok.isdigit() and i + 1 < len(tokens) and (">" in tokens[i + 1] or "<" in tokens[i + 1]):
            continue  # the fd of `2>&1`
        else:
            words.append(tok)
    out.append((words, ""))
    return out


def parse_codex_args(args: list[str]) -> tuple[list[str], str | None]:
    """Split codex args into positional words and the `-o` value (flags and their values are dropped)."""
    positional: list[str] = []
    output: str | None = None
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("-") and tok != "-":
            name, eq, value = tok.partition("=")
            if name in CODEX_OUTPUT_OPTS:
                if eq:
                    output = value
                elif i + 1 < len(args):
                    output = args[i + 1]
            if not eq and name in CODEX_VALUE_OPTS:
                i += 1
        else:
            positional.append(tok)
        i += 1
    return positional, output


def expand_path(path: str, env: dict[str, str]) -> str | None:
    """Expand $VAR / ${VAR} (from assignments seen in the command, then the environment) and ~."""

    def sub(m: re.Match[str]) -> str:
        name = m.group(1) or m.group(2)
        return env.get(name, os.environ.get(name, m.group(0)))

    path = os.path.expanduser(re.sub(r"\$(?:\{(\w+)\}|(\w+))", sub, path))
    return None if "$" in path or "`" in path else path


def codex_reviews_in_command(command: str, depth: int = 0) -> list[CodexReview]:
    """The `codex exec`/`codex review` code reviews that `command` runs (not `codex --version`, not mere text)."""
    reviews: list[CodexReview] = []
    env: dict[str, str] = {}
    for words, terminator in split_simple_commands(command):
        if words[:1] == ["export"]:
            words = words[1:]
        while words and re.match(r"[A-Za-z_]\w*=", words[0]):  # leading VAR=value
            name, _, value = words.pop(0).partition("=")
            env[name] = value
        # nohup / env / timeout 600 / npx -y ... in front of codex
        while words and os.path.basename(words[0]) in WRAPPER_COMMANDS:
            words.pop(0)
            while words and (words[0].startswith("-") or re.match(r"[A-Za-z_]\w*=|\d+[smhd]?$", words[0])):
                words.pop(0)
        if not words:
            continue
        exe = os.path.basename(words[0])
        if exe in SHELLS and depth < 2 and "-c" in words[1:-1]:  # bash -c "codex exec ..."
            inner = words[words.index("-c") + 1]
            for r in codex_reviews_in_command(inner, depth + 1):
                reviews.append(CodexReview(r.output_file, r.background or terminator == "&"))
            continue
        if exe != "codex":
            continue
        args = words[1:]
        if CODEX_HELP_FLAGS & set(args):
            continue
        positional, output = parse_codex_args(args)
        if not positional:
            continue
        sub, rest = positional[0], positional[1:]
        if sub in ("exec", "e"):
            if rest[:1] == ["review"]:
                sub = "review"
            elif rest[:1] and rest[0] in ("resume", "fork", "help"):
                continue
            else:
                prompt = " ".join(rest)
                # no prompt argument / "-": the prompt arrives on stdin (heredoc, pipe), so look at the whole command
                if not CODEX_REVIEW_PROMPT.search(command if prompt in ("", "-") else prompt):
                    continue
                sub = "review"
        if sub == "review":
            reviews.append(CodexReview(expand_path(output, env) if output else None, terminator == "&"))
    return reviews


def parse_timestamp(value: object) -> float | None:
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


def output_file_written(path: str, cwd: str, started: float | None) -> bool:
    """codex writes `-o <file>` when the review is done: it must exist, be non-empty and be newer than the call."""
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        st = os.stat(full)
    except OSError:
        return False
    return st.st_size > 0 and (started is None or st.st_mtime >= started - 2)


def codex_review_ran_in(path: str) -> bool:
    """True when the transcript at `path` holds a codex code review that finished (see module docstring)."""
    calls: dict[str, tuple[list[CodexReview], bool, str, float | None]] = {}
    errors: dict[str, bool] = {}  # tool_use id -> tool_result is_error
    notifications: dict[str, str] = {}  # tool_use id -> task-notification status
    try:
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                if "codex" not in line and "tool_result" not in line and "task-notification" not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                message = row.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if row.get("type") == "queue-operation":
                    content = row.get("content")
                if isinstance(content, str):
                    if "<task-notification>" in content:
                        for m in TASK_NOTIFICATION.finditer(content):
                            notifications[m.group(1).strip()] = m.group(2).strip()
                    continue
                for block in content if isinstance(content, list) else []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and block.get("name") == "Bash":
                        tool_input = block.get("input") or {}
                        reviews = codex_reviews_in_command(str(tool_input.get("command", "")))
                        if reviews:
                            calls[block.get("id", "")] = (
                                reviews,
                                bool(tool_input.get("run_in_background")),
                                str(row.get("cwd") or os.getcwd()),
                                parse_timestamp(row.get("timestamp")),
                            )
                    elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                        errors[block["tool_use_id"]] = bool(block.get("is_error"))
    except OSError:
        return False

    for tool_id, (reviews, run_in_background, cwd, started) in calls.items():
        for review in reviews:
            if review.output_file and output_file_written(review.output_file, cwd, started):
                return True
            if run_in_background:
                if notifications.get(tool_id) == "completed":
                    return True
            elif not review.background and tool_id in errors and not errors[tool_id]:
                return True  # ran in the foreground and exited 0
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
        if codex_review_ran_in(path):
            return True
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
        "Blocked: this command publishes/completes a PR, but neither /code-review nor "
        "/bms-code-review has been run yet in this session (directly or via a subagent), and no completed "
        "`codex exec`/`codex review` code review was found either. Run one of them first, then retry. "
        "A codex review counts once it has finished: run it in the foreground, or in the background with "
        "`-o <file>` so the output file proves completion."
    )


if __name__ == "__main__":
    main()
