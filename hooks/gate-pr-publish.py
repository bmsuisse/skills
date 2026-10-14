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

AND that review is known to have finished (a mere start proves nothing). How that is proven depends on how it ran:

  - in the foreground: the Bash tool_result is not an error (codex exits non-zero on failure);
  - with run_in_background: a later <task-notification> for that tool call says "completed";
  - in the background of the shell (`nohup codex exec ... -o out.md > log 2>&1 &`; the tool_result only says
    "started"): ONLY the `-o <file>` output file counts. It must exist, be non-empty and be newer than the call's
    transcript timestamp (codex writes it when the review is done). Without `-o`, or without a valid timestamp on
    the call, such a run cannot be proven finished and does not count. An `-o` file never rescues a foreground
    or run_in_background call: a failed run can leave a partial file behind.

For the two non-shell-backgrounded cases the tool result is the exit status of the WHOLE command line, so it only
proves codex succeeded when the codex call decides that status. That holds when the codex command is the last
command of the line (`cd x && codex exec ...`, `codex exec ... && echo ok`, `echo p | codex exec -`, a trailing `;`) and
fails when something can mask it, so the run is conservatively NOT accepted:

  - a pipeline after codex without `set -o pipefail` earlier in the command (`codex review | cat`,
    `codex exec ... | tee out.md`; the status is the last command's). With pipefail it is accepted;
  - another command after a `;` or newline (`codex exec ...; echo done`);
  - an `||` in the same and/or list (`codex exec ... || true`, `a || codex exec ...`).

For such runs use `-o` plus `&`, or drop the tail. The prompt of `codex exec` may come from a variable assigned
earlier in the same command (`P="...code review..."; codex exec "$P"`); unresolved variables do not count.

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


CONNECTORS = {"&&", "||", "|", "|&"}  # join simple commands into one and/or list (or pipeline)
REDIRECT = re.compile(r"^\d*(?:>>?|<<?<?|>&|<&|&>>?|>\|)(.*)$", re.DOTALL)
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1")
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")


@dataclass
class CodexReview:
    output_file: str | None  # expanded `-o` path, None when absent or not resolvable
    background: bool  # backgrounded by the shell (`&`): the Bash tool_result only says "started"
    status_visible: (
        bool  # foreground: the command line's exit status is codex's (not masked by `| cat`, `; echo`, `|| true`)
    )


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies (`codex exec - <<'EOF' ... EOF`) so their lines are not parsed as shell commands."""
    out: list[str] = []
    pending: list[tuple[str, bool]] = []  # delimiters of the heredocs opened on the previous lines
    for line in command.split("\n"):
        if pending:
            delim, dash = pending[0]
            if (line.strip() if dash else line) == delim:
                pending.pop(0)
            continue
        out.append(line)
        pending = [(m.group(2), "<<-" in m.group(0)) for m in HEREDOC.finditer(line)]
    return "\n".join(out)


def split_simple_commands(command: str) -> list[tuple[list[str], str]]:
    """Split a shell command line into (words, connector) pairs, e.g. (["codex", "exec", ...], "&").

    The connector is what follows the command: ";" (also a newline), "&", "&&", "||", "|", "|&" or "" (end).
    Redirections are dropped; parentheses are ignored.
    """
    lexer = shlex.shlex(strip_heredocs(command), posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    out: list[tuple[list[str], str]] = []
    words: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if tok and set(tok) <= SHELL_PUNCT:
            connector = tok.replace("\n", "").replace("(", "").replace(")", "")
            if connector == "&" and i < len(tokens) and tokens[i].startswith(">"):
                continue  # `&> file` redirects both streams, it does not background anything
            if not connector and "\n" in tok:
                connector = ";"
            if connector:
                out.append((words, connector))
                words = []
            continue
        m = REDIRECT.match(tok)
        if m:
            if not m.group(1):  # target is the next token; `>&` / `2>&1` lex as `>`, `&`, `1`
                if i < len(tokens) and tokens[i] == "&":
                    i += 1
                i += 1
            continue
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


def expand_vars(text: str, env: dict[str, str], use_environ: bool = False) -> str:
    """Substitute $VAR / ${VAR} from the assignments seen in the command (optionally the environment too)."""

    def sub(m: re.Match[str]) -> str:
        name = m.group(1) or m.group(2)
        if name in env:
            return env[name]
        return os.environ.get(name, m.group(0)) if use_environ else m.group(0)

    return re.sub(r"\$(?:\{(\w+)\}|(\w+))", sub, text)


def expand_path(path: str, env: dict[str, str]) -> str | None:
    """Expand variables (assignments seen in the command, then the environment) and ~."""
    path = os.path.expanduser(expand_vars(path, env, use_environ=True))
    return None if "$" in path or "`" in path else path


def list_bounds(segments: list[tuple[list[str], str]], idx: int) -> tuple[int, int]:
    """First and last segment of the and/or list / pipeline that segment `idx` belongs to."""
    start = end = idx
    while start > 0 and segments[start - 1][1] in CONNECTORS:
        start -= 1
    while end < len(segments) - 1 and segments[end][1] in CONNECTORS:
        end += 1
    return start, end


def status_is_codex(segments: list[tuple[list[str], str]], idx: int, pipefail: bool) -> bool:
    """True when the exit status of the whole command line is the exit status of segment `idx` (a codex call).

    Not the case when codex is piped into something (without pipefail), when a later `;`/newline command follows,
    or when an `||` in its and/or list can swallow its failure. `a && codex`, `codex && b` and `x | codex` are fine:
    the line only exits 0 when codex did.
    """
    start, end = list_bounds(segments, idx)
    if any(segments[k][1] == "||" for k in range(start, end)):
        return False
    if segments[idx][1] in ("|", "|&") and not pipefail:
        return False
    return not any(words for words, _ in segments[end + 1 :])


def codex_reviews_in_command(command: str, depth: int = 0, pipefail: bool = False) -> list[CodexReview]:
    """The `codex exec`/`codex review` code reviews that `command` runs (not `codex --version`, not mere text)."""
    reviews: list[CodexReview] = []
    env: dict[str, str] = {}
    segments = split_simple_commands(command)
    for idx, (words, connector) in enumerate(segments):
        words = list(words)
        if words[:1] == ["export"]:
            words = words[1:]
        assigned: dict[str, str] = {}
        while words and ASSIGNMENT.match(words[0]):  # leading VAR=value
            name, _, value = words.pop(0).partition("=")
            assigned[name] = expand_vars(value, env)
        if not words:
            env.update(assigned)  # a plain assignment is visible to the following commands, `VAR=x cmd` is not
            continue
        if words[0] == "set":  # set -o pipefail / set -euo pipefail / set +o pipefail
            for k, w in enumerate(words[1:], start=1):
                if w == "pipefail" and k > 1 and (m := re.fullmatch(r"([-+])[A-Za-z]*o", words[k - 1])):
                    pipefail = m.group(1) == "-"
            continue
        # nohup / env / timeout 600 / npx -y ... in front of codex
        while words and os.path.basename(words[0]) in WRAPPER_COMMANDS:
            words.pop(0)
            while words and (words[0].startswith("-") or re.match(r"[A-Za-z_]\w*=|\d+[smhd]?$", words[0])):
                words.pop(0)
        if not words:
            continue
        start, end = list_bounds(segments, idx)
        shell_background = segments[end][1] == "&"
        visible = status_is_codex(segments, idx, pipefail)
        exe = os.path.basename(words[0])
        if exe in SHELLS and depth < 2 and "-c" in words[1:-1]:  # bash -c "codex exec ..."
            inner = words[words.index("-c") + 1]
            inner_pipefail = "pipefail" in words and "-o" in words  # bash -o pipefail -c ...
            for r in codex_reviews_in_command(inner, depth + 1, inner_pipefail):
                reviews.append(
                    CodexReview(r.output_file, r.background or shell_background, r.status_visible and visible)
                )
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
                prompt = expand_vars(" ".join(rest), env)
                # no prompt argument / "-": the prompt arrives on stdin (heredoc, pipe), so look at the whole command
                if not CODEX_REVIEW_PROMPT.search(command if prompt in ("", "-") else prompt):
                    continue
                sub = "review"
        if sub == "review":
            reviews.append(CodexReview(expand_path(output, env) if output else None, shell_background, visible))
    return reviews


def parse_timestamp(value: object) -> float | None:
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def output_file_written(path: str, cwd: str, started: float | None) -> bool:
    """codex writes `-o <file>` when the review is done: it must exist, be non-empty and be newer than the call."""
    if started is None:  # without the call's timestamp "newer than the call" cannot be told
        return False
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        st = os.stat(full)
    except (OSError, ValueError):  # ValueError: embedded NUL byte
        return False
    return st.st_size > 0 and st.st_mtime >= started


def review_finished(
    review: CodexReview, run_in_background: bool, notification: str | None, is_error: bool | None, cwd: str,
    started: float | None,
) -> bool:  # fmt: skip
    if review.background:  # `... &`: the tool_result says nothing about the review, only its output file does
        return review.output_file is not None and output_file_written(review.output_file, cwd, started)
    if not review.status_visible:  # `codex review | cat`, `codex exec ...; echo done`: the result may hide a failure
        return False
    if run_in_background:
        return notification == "completed"
    return is_error is False  # ran in the foreground and exited 0


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
                    scan_row(json.loads(line), calls, errors, notifications)
                except Exception:  # a malformed line must not break the scan of the others
                    continue
    except OSError:
        return False

    for tool_id, (reviews, run_in_background, cwd, started) in calls.items():
        for review in reviews:
            if review_finished(
                review, run_in_background, notifications.get(tool_id), errors.get(tool_id), cwd, started
            ):
                return True
    return False


def scan_row(row: object, calls: dict, errors: dict[str, bool], notifications: dict[str, str]) -> None:
    """Collect codex Bash calls, tool results and background-task notifications from one transcript row."""
    if not isinstance(row, dict):
        return
    message = row.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if row.get("type") == "queue-operation":
        content = row.get("content")
    if isinstance(content, str):
        if "<task-notification>" in content:
            for m in TASK_NOTIFICATION.finditer(content):
                notifications[m.group(1).strip()] = m.group(2).strip()
        return
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use" and block.get("name") == "Bash":
            tool_input = block.get("input")
            if not isinstance(tool_input, dict):
                continue
            reviews = codex_reviews_in_command(str(tool_input.get("command", "")))
            if reviews:
                calls[str(block.get("id", ""))] = (
                    reviews,
                    bool(tool_input.get("run_in_background")),
                    str(row.get("cwd") or os.getcwd()),
                    parse_timestamp(row.get("timestamp")),
                )
        elif block.get("type") == "tool_result" and str(block.get("tool_use_id")) in calls:
            errors[str(block["tool_use_id"])] = bool(block.get("is_error"))


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
        "A codex review counts once it has finished: run it in the foreground as the last command of the line "
        "(no `| tee`, `; echo` or `|| true` after it, which would hide a failure), or backgrounded with `&` "
        "and `-o <file>` so the output file proves completion."
    )


if __name__ == "__main__":
    main()
