#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: blocks hand-wired PR / CI watch scripts and points to `bdt`.

`bdt pr status --wait`, `bdt pr info`, `bdt pr retry` and `bdt pr watch-deploy` already answer "is the PR green?" for
Azure DevOps and GitHub. Agents still glue their own from `az repos pr show`, `az pipelines runs list`, `curl` against
`_apis/build/builds` and a `sleep` loop, which burns context on every poll and misreads the build state. Denied:

  - a polling construct (`while`/`until`/`for` loop, `sleep`, `watch`) around a PR or CI status query;
  - a CI status query on its own: `az pipelines runs list|show`, `az pipelines build list|show`, `gh run list|view|watch`,
    `gh pr checks`, or the Azure DevOps build API (`_apis/build/builds`, except logs/artifacts/attachments).

A single `az repos pr show`/`list` or pull request REST call stays allowed (labels, threads and attachments have no
`bdt` command). Only commands that run something are scanned: `echo`, `git commit -m` or a heredoc written to a file
that merely mention these commands are not.
"""

import json
import os
import re
import shlex
import shutil
import sys

ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1")
WRAPPERS = {"nohup", "setsid", "time", "command", "exec", "env", "sudo", "timeout", "xargs", "builtin"}
KEYWORDS = {"if", "then", "else", "elif", "do", "!", "{", "}"}
LOOPS = {"while", "until", "for"}
SHELL_PUNCT = set(";&|()\n")
# commands that run what they are given, so what they are given is worth scanning
RUNNERS = {"eval", "az", "curl", "wget", "http", "https", "gh", "python", "python3", "uv", "uvx", "bun", "bunx", "node", "bash", "sh", "zsh"}
INTERPRETERS = re.compile(r"\b(python3?|bash|sh|zsh|node|bun|uv)\b")

# words may be separated by whitespace or by the quotes/commas of an argument list (`['az', 'repos', 'pr', 'show']`)
SEP = r"[\s'\",\[\]]+"


def words(*parts: str) -> str:
    return r"\b" + SEP.join(parts)


PR_QUERY = re.compile(
    words("az", "repos", "pr", "(show|list)") + r"\b"
    r"|" + words("az", "devops", "invoke") + r"\b[^\n]*\b(pull_?requests?|build)\b"
    r"|_apis/git/[^\s'\"]*pull_?requests\b"
    r"|" + words("gh", "pr", "(view|status|checks)") + r"\b",
    re.IGNORECASE,
)
CI_QUERY = re.compile(
    words("az", "pipelines", "(runs|build)", "(list|show)") + r"\b"
    r"|" + words("gh", "run", "(list|view|watch)") + r"\b"
    r"|" + words("gh", "pr", "checks") + r"\b"
    r"|_apis/build/builds(?!/\d+/(logs|artifacts|attachments)\b)",
    re.IGNORECASE,
)
SUBSHELL = re.compile(r"\$\((.*)\)|`(.*)`", re.DOTALL)
POLL_TEXT = re.compile(r"\bsleep\b|\bsetTimeout\b|\bwatch\s+-n\b", re.IGNORECASE)


def split_heredocs(command: str) -> tuple[str, list[str]]:
    """Separate heredoc bodies from the command line; bodies fed to an interpreter (`python3 - <<EOF`) run, so they are returned."""
    out: list[str] = []
    scripts: list[str] = []
    pending: list[tuple[str, bool, bool]] = []
    for line in command.split("\n"):
        if pending:
            delim, dash, runs = pending[0]
            if (line.strip() if dash else line) == delim:
                pending.pop(0)
            elif runs:
                scripts.append(line)
            continue
        out.append(line)
        runs = bool(INTERPRETERS.search(line))
        pending = [(m.group(2), "<<-" in m.group(0), runs) for m in HEREDOC.finditer(line)]
    return "\n".join(out), scripts


def split_simple_commands(command: str) -> list[list[str]]:
    """Split a command line into simple commands, respecting quotes and line continuations."""
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


def scan_text(text: str) -> tuple[bool, bool, bool]:
    return bool(POLL_TEXT.search(text)), bool(PR_QUERY.search(text)), bool(CI_QUERY.search(text))


def scan(command: str) -> tuple[bool, bool, bool]:
    """Return (polls, pr_query, ci_query) for the commands that actually run something."""
    command, scripts = split_heredocs(command.replace("\\\n", ""))
    polls = pr_query = ci_query = False
    for script in scripts:
        found = scan_text(script)
        polls, pr_query, ci_query = polls or found[0], pr_query or found[1], ci_query or found[2]
    simple = split_simple_commands(command)
    # `B=https://.../_apis/build/builds; curl "$B/1/timeline"`: the URL is assigned apart from the call
    assigned = {t.split("=", 1)[0]: t for tokens in simple for t in tokens if ASSIGNMENT.match(t)}
    for tokens in simple:
        while tokens and (ASSIGNMENT.match(tokens[0]) or tokens[0] in KEYWORDS or tokens[0] in LOOPS):
            polls = polls or tokens[0] in LOOPS
            tokens = tokens[1:]
        if tokens and tokens[0] in WRAPPERS:
            # wrapper options may take values (`env -u VAR`, `timeout 5`), so look for the command after it
            tokens = tokens[next((i for i, t in enumerate(tokens) if t in RUNNERS | {"sleep", "watch"}), len(tokens)) :]
        if not tokens:
            continue
        if tokens[0] in {"sleep", "watch"}:
            polls = True
        for token in tokens:
            # `[ "$(az repos pr show ...)" = completed ]`
            for m in SUBSHELL.finditer(token):
                found = scan(m.group(1) or m.group(2))
                polls, pr_query, ci_query = polls or found[0], pr_query or found[1], ci_query or found[2]
        if tokens[0] in RUNNERS | {"watch"}:
            text = " ".join(tokens)
            used = " ".join(v for k, v in assigned.items() if re.search(rf"\${{?{k}\b", text))
            found = scan_text(f"{used} {text}")
            polls, pr_query, ci_query = polls or found[0], pr_query or found[1], ci_query or found[2]
    return polls, pr_query, ci_query


def should_block(command: str) -> bool:
    polls, pr_query, ci_query = scan(command)
    return ci_query or (polls and pr_query)


def bdt_hint() -> str:
    if shutil.which("bdt"):
        return ""
    if os.path.exists(os.path.expanduser("~/.local/bin/bdt")):
        return " `bdt` is installed in ~/.local/bin but not on PATH: `export PATH=\"$HOME/.local/bin:$PATH\"`."
    return " `bdt` is not installed: `uv tool install bmsdna-devtools` (update with `uv tool upgrade bmsdna-devtools`)."


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    if data.get("tool_name") != "Bash":
        return

    if not should_block(data.get("tool_input", {}).get("command", "")):
        return

    reason = (
        "Blocked: don't hand-wire PR/CI watch scripts (`az repos pr show`, `az pipelines runs`, `curl` on the build API, "
        "`sleep` loops). Use bdt, it works for Azure DevOps and GitHub: `bdt pr status --wait --timeout 540` waits for "
        "the checks and lists the failing ones (exit 4 = still running, re-run it; 3 = needs manual approval; 1 = a check "
        "failed), `bdt pr info [--pr-id N]` gives state, build state and closed issues, `bdt pr retry` re-runs only the "
        "failed jobs, `bdt pr watch-deploy --target-branch <branch>` follows the pipeline that runs after the merge. "
        "In the dev-workflow, dispatch the `bms-ci-watch` agent instead of polling yourself. If bdt cannot answer what "
        "you need, say so to the user rather than scripting around it." + bdt_hint()
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
