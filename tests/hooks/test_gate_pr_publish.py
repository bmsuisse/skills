"""Tests for the gate-pr-publish PreToolUse hook."""

import functools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "gate-pr-publish.py"


@functools.cache
def failing_cli_dir() -> Path:
    """`gh`/`az` stand-ins that exit 1, so the promotion lookup never reaches the network and finds nothing."""
    bin_dir = Path(tempfile.mkdtemp(prefix="failing-cli-"))
    for name in ("gh", "az"):
        (bin_dir / name).write_text("#!/bin/sh\nexit 1\n")
        (bin_dir / name).chmod(0o755)
    return bin_dir


def run_hook(
    transcript: Path, command: str = "bdt pr publish", cwd: Path | None = None, path_prefix: Path | None = None
) -> dict | None:
    payload_data: dict = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "transcript_path": str(transcript),
    }
    if cwd:
        payload_data["cwd"] = str(cwd)
    env = {**os.environ, "PATH": f"{path_prefix or failing_cli_dir()}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload_data),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def transcript_with(tmp_path: Path, skill: str | None) -> Path:
    path = tmp_path / "session.jsonl"
    lines = [json.dumps({"type": "user", "message": "hi"})]
    if skill:
        lines.append(json.dumps({"name": "Skill", "input": {"skill": skill}}))
    path.write_text("\n".join(lines))
    return path


@pytest.mark.parametrize(
    "skill", ["code-review", "bms-code-review", "plugin:code-review", "dev-workflow:bms-code-review"]
)
def test_allows_after_review(tmp_path, skill):
    assert run_hook(transcript_with(tmp_path, skill)) is None


def assert_denied(out: dict | None) -> None:
    assert out is not None
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("skill", [None, "bms-plan-review", "design-review"])
def test_denies_without_review(tmp_path, skill):
    assert_denied(run_hook(transcript_with(tmp_path, skill)))


# --- reviews done through the codex CLI --------------------------------------------------------------------------

REVIEW_PROMPT = "Use the bms-code-review skill (full mode, --full) on the diff against origin/main. Review only."


def bash_call(command: str, tool_id: str = "toolu_1", background: bool = False, timestamp: str | None = None) -> dict:
    tool_input: dict = {"command": command}
    if background:
        tool_input["run_in_background"] = True
    row = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": tool_id, "name": "Bash", "input": tool_input}],
        },
    }
    if timestamp:
        row["timestamp"] = timestamp
    return row


def bash_result(tool_id: str = "toolu_1", text: str = "ok", is_error: bool = False) -> dict:
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": text, "is_error": is_error}
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def task_notification(tool_id: str, status: str) -> dict:
    text = (
        f"<task-notification>\n<task-id>b1</task-id>\n<tool-use-id>{tool_id}</tool-use-id>\n"
        f"<status>{status}</status>\n<summary>Background command finished</summary>\n</task-notification>"
    )
    return {"type": "user", "message": {"role": "user", "content": text}}


def transcript_rows(tmp_path: Path, *rows: dict, name: str = "session.jsonl") -> Path:
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(r) for r in [{"type": "user", "message": "hi"}, *rows]))
    return path


def codex_foreground(tmp_path: Path, command: str, **result) -> Path:
    return transcript_rows(tmp_path, bash_call(command), bash_result(**result))


@pytest.mark.parametrize(
    "command",
    [
        f'codex exec -C /work/wt -s read-only "{REVIEW_PROMPT}"',
        f'cd /work/wt && codex exec -s read-only --skip-git-repo-check -o /tmp/out.md "{REVIEW_PROMPT}"',
        'codex exec "Do a code review of the staged changes"',
        'codex e "/code-review"',
        'codex exec "Review the diff of the current branch against main (git diff main...HEAD) for correctness bugs only."',
        'timeout 590 codex exec -s read-only "Review this pull request for bugs"',
        'codex exec "Please review my latest commit"',
        "codex review",
        "codex review --base main",
        "codex exec review --uncommitted",
        f'set -o pipefail; /usr/local/bin/codex exec "{REVIEW_PROMPT}" | tail -40',
        f'set -euo pipefail\ncodex exec "{REVIEW_PROMPT}" 2>&1 | tee /tmp/out.md',
        f'cd /work/wt && codex exec "{REVIEW_PROMPT}"',
        f'cd /work/wt && codex exec "{REVIEW_PROMPT}" > /tmp/codex.log 2>&1',
        f'codex exec "{REVIEW_PROMPT}" && echo review done',
        f'codex exec "{REVIEW_PROMPT}";',
        f'nohup codex exec "{REVIEW_PROMPT}"',
        f'timeout 900 env CODEX_HOME=/x codex exec "{REVIEW_PROMPT}"',
        f"bash -c 'codex exec \"{REVIEW_PROMPT}\"'",
        f'echo starting; codex exec -m gpt-5 "{REVIEW_PROMPT}"',
        "echo 'please do a code review' | codex exec -",
        "codex exec - <<'EOF'\nPlease do a code review of the diff.\nEOF",
        f'PROMPT="{REVIEW_PROMPT}"; codex exec -s read-only "$PROMPT"',
        f'export P="{REVIEW_PROMPT}"\ncd /work/wt && codex exec "${{P}}"',
        'A="Use the bms-code-review skill"; B="$A on the diff"; codex exec "$B"',
    ],
)
def test_allows_after_completed_foreground_codex_review(tmp_path, command):
    assert run_hook(codex_foreground(tmp_path, command)) is None


def test_allows_codex_review_run_by_a_subagent(tmp_path):
    transcript = transcript_with(tmp_path, None)
    sub = tmp_path / "session" / "subagents"
    sub.mkdir(parents=True)
    transcript_rows(sub, bash_call("codex review --base main"), bash_result(), name="agent-1.jsonl")
    assert run_hook(transcript) is None


def background_start(tmp_path: Path, out: Path | None, timestamp: str | None = "2020-01-01T00:00:00Z") -> Path:
    """The shape of a real run: `nohup codex exec ... -o $S/x.md > log 2>&1 &`, tool_result only says "started"."""
    o = f"-o $S/{out.name} " if out else ""
    command = (
        f'S={tmp_path}; nohup codex exec -C "$PWD" -s read-only --skip-git-repo-check {o}"{REVIEW_PROMPT}" '
        "> $S/codex.log 2>&1 &\necho started; sleep 1"
    )
    return transcript_rows(tmp_path, bash_call(command, timestamp=timestamp), bash_result(text="started"))


def test_allows_background_codex_review_once_the_output_file_is_written(tmp_path):
    out = tmp_path / "codex-review.md"
    out.write_text("## Should fix\n- nothing\n")
    assert run_hook(background_start(tmp_path, out)) is None


def test_denies_background_codex_review_while_the_output_file_is_missing(tmp_path):
    out = tmp_path / "codex-review.md"
    assert_denied(run_hook(background_start(tmp_path, out)))


def test_denies_background_codex_review_with_empty_output_file(tmp_path):
    out = tmp_path / "codex-review.md"
    out.write_text("")
    assert_denied(run_hook(background_start(tmp_path, out)))


def test_denies_background_codex_review_with_stale_output_file(tmp_path):
    out = tmp_path / "codex-review.md"
    out.write_text("an older review")
    assert_denied(run_hook(background_start(tmp_path, out, timestamp="2999-01-01T00:00:00Z")))


@pytest.mark.parametrize("timestamp", [None, "", "not a date"])
def test_denies_background_codex_review_without_a_valid_call_timestamp(tmp_path, timestamp):
    # "newer than the call" cannot be told, so an existing non-empty file proves nothing
    out = tmp_path / "codex-review.md"
    out.write_text("## Should fix\n- nothing\n")
    assert_denied(run_hook(background_start(tmp_path, out, timestamp=timestamp)))


def test_denies_background_codex_review_without_output_file(tmp_path):
    # Nothing proves that a nohup'd run without -o ever finished.
    assert_denied(run_hook(background_start(tmp_path, None)))


def test_allows_run_in_background_codex_review_after_completed_notification(tmp_path):
    command = f'codex exec "{REVIEW_PROMPT}"'
    transcript = transcript_rows(
        tmp_path,
        bash_call(command, background=True),
        bash_result(text="Command running in background with ID: b1"),
        task_notification("toolu_1", "completed"),
    )
    assert run_hook(transcript) is None


@pytest.mark.parametrize(
    "notification", [None, ("toolu_1", "killed"), ("toolu_1", "failed"), ("toolu_other", "completed")]
)
def test_denies_run_in_background_codex_review_without_completion(tmp_path, notification):
    rows = [
        bash_call(f'codex exec "{REVIEW_PROMPT}"', background=True),
        bash_result(text="Command running in background"),
    ]
    if notification:
        rows.append(task_notification(*notification))
    assert_denied(run_hook(transcript_rows(tmp_path, *rows)))


@pytest.mark.parametrize(
    "command",
    [
        "codex --version",
        "codex exec --help",
        "codex review --help",
        "which codex; codex --version 2>&1 | head -2",
        'codex exec "fix the failing test in cli.py"',
        'codex exec "review the README wording"',
        'echo "Summarize this text" | codex exec - -o /tmp/review-diff.md',
        'codex exec "write a changes summary for the diff"',
        'codex exec resume --last "code review"',
        'codex login --code-review "x"',
        "codex exec - < prompt.md",
        'git commit -m "codex exec: use the bms-code-review skill"',
        f'echo "codex exec \\"{REVIEW_PROMPT}\\""',
        'grep -rn "codex review" docs/',
        'gh pr comment --body "codex review looks fine, code review done"',
        'cat notes.md  # codex exec "code review"',
        'codexec "code review"',
        "ls ~/.codex/skills/bms-code-review",
    ],
)
def test_denies_codex_commands_that_are_not_a_review(tmp_path, command):
    assert_denied(run_hook(codex_foreground(tmp_path, command)))


def test_denies_codex_review_that_failed(tmp_path):
    assert_denied(run_hook(codex_foreground(tmp_path, "codex review", text="Exit code 1", is_error=True)))


def test_denies_codex_review_without_a_tool_result(tmp_path):
    assert_denied(run_hook(transcript_rows(tmp_path, bash_call("codex review"))))


def test_denies_when_codex_is_only_mentioned_in_text(tmp_path):
    text = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "codex exec code review done"}]},
    }
    assert_denied(run_hook(transcript_rows(tmp_path, text)))


def test_denies_codex_review_in_a_non_bash_tool(tmp_path):
    row = bash_call("codex review")
    row["message"]["content"][0]["name"] = "Write"
    assert_denied(run_hook(transcript_rows(tmp_path, row, bash_result())))


# --- completion proof: the -o file only counts for shell-backgrounded runs -----------------------------------------


def test_denies_failed_foreground_codex_review_that_left_an_output_file(tmp_path):
    out = tmp_path / "report.md"
    out.write_text("## partial output of a run that then failed\n")
    command = f"codex review -o {out} --base main"
    transcript = transcript_rows(
        tmp_path,
        bash_call(command, timestamp="2020-01-01T00:00:00Z"),
        bash_result(text="Exit code 1", is_error=True),
    )
    assert_denied(run_hook(transcript))


@pytest.mark.parametrize("status", ["failed", "killed", None])
def test_denies_run_in_background_codex_review_with_output_file_but_no_completion(tmp_path, status):
    out = tmp_path / "report.md"
    out.write_text("## partial output\n")
    rows = [
        bash_call(f'codex exec -o {out} "{REVIEW_PROMPT}"', background=True, timestamp="2020-01-01T00:00:00Z"),
        bash_result(text="Command running in background with ID: b1"),
    ]
    if status:
        rows.append(task_notification("toolu_1", status))
    assert_denied(run_hook(transcript_rows(tmp_path, *rows)))


def test_denies_foreground_codex_review_with_output_file_but_no_tool_result(tmp_path):
    out = tmp_path / "report.md"
    out.write_text("## partial output\n")
    call = bash_call(f'codex exec -o {out} "{REVIEW_PROMPT}"', timestamp="2020-01-01T00:00:00Z")
    assert_denied(run_hook(transcript_rows(tmp_path, call)))


def test_allows_shell_backgrounded_codex_review_with_fresh_output_file_in_a_run_in_background_call(tmp_path):
    out = tmp_path / "report.md"
    out.write_text("## Should fix\n- nothing\n")
    command = f'nohup codex exec -o {out} "{REVIEW_PROMPT}" > {tmp_path}/log 2>&1 &'
    call = bash_call(command, background=True, timestamp="2020-01-01T00:00:00Z")
    assert run_hook(transcript_rows(tmp_path, call, bash_result(text="started"))) is None


@pytest.mark.parametrize("redirect", ["&>/dev/null", ">/dev/null 2>&1", "> /dev/null 2>&1"])
def test_recognizes_shell_backgrounding_after_redirections(tmp_path, redirect):
    out = tmp_path / "report.md"
    out.write_text("## Should fix\n- nothing\n")
    command = f'codex exec -o {out} "{REVIEW_PROMPT}" {redirect} &'
    call = bash_call(command, timestamp="2020-01-01T00:00:00Z")
    assert run_hook(transcript_rows(tmp_path, call, bash_result(text="started"))) is None


# --- completion proof: the tool result must reflect codex's own exit status -------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "codex review | cat",
        "codex review --base main 2>&1 | tail -40",
        f'codex exec "{REVIEW_PROMPT}" | tee out.md',
        f'codex exec "{REVIEW_PROMPT}" |& tee out.md',
        f'set +o pipefail; codex exec "{REVIEW_PROMPT}" | tee out.md',
        f'codex exec "{REVIEW_PROMPT}"; echo done',
        f'codex exec "{REVIEW_PROMPT}"\necho done',
        f'codex exec "{REVIEW_PROMPT}" || true',
        f'codex exec "{REVIEW_PROMPT}" && echo ok || echo failed',
        f'true || codex exec "{REVIEW_PROMPT}"',
        f'(codex exec "{REVIEW_PROMPT}"; echo done)',
        f"bash -c 'codex exec \"{REVIEW_PROMPT}\" | tee out.md'",
        f"bash -c 'codex exec \"{REVIEW_PROMPT}\"; echo done'",
        f"bash -c 'codex exec \"{REVIEW_PROMPT}\"' || true",
    ],
)
def test_denies_codex_review_whose_failure_the_tool_result_would_hide(tmp_path, command):
    # the Bash result is the status of the whole command line: `| cat` / `; echo done` / `|| true` exit 0 anyway
    assert_denied(run_hook(codex_foreground(tmp_path, command)))
    background = transcript_rows(
        tmp_path,
        bash_call(command, background=True),
        bash_result(text="Command running in background"),
        task_notification("toolu_1", "completed"),
        name="background.jsonl",
    )
    assert_denied(run_hook(background))


def test_pipefail_inside_bash_c_counts_for_that_shell_only(tmp_path):
    ok = f"bash -c 'set -o pipefail; codex exec \"{REVIEW_PROMPT}\" | tee out.md'"
    assert run_hook(codex_foreground(tmp_path, ok)) is None
    outer = f"set -o pipefail; bash -c 'codex exec \"{REVIEW_PROMPT}\" | tee out.md'"
    assert_denied(run_hook(codex_foreground(tmp_path, outer)))


def test_denies_a_failed_foreground_run_even_when_the_codex_call_decides_the_status(tmp_path):
    command = f'cd /work/wt && codex exec "{REVIEW_PROMPT}"'
    assert_denied(run_hook(codex_foreground(tmp_path, command, text="Exit code 1", is_error=True)))


# --- the prompt may come from a variable assigned in the same command --------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        'codex exec "$UNSET"',
        'PROMPT="fix the failing test"; codex exec "$PROMPT"',
        f'codex exec "$PROMPT"; PROMPT="{REVIEW_PROMPT}"',  # assigned too late
        f'PROMPT="{REVIEW_PROMPT}" codex exec "$PROMPT"',  # a prefix assignment is not visible to its own arguments
        f'PROMPT="{REVIEW_PROMPT}"; codex exec "$OTHER"',
        # an unresolved variable is not rescued by a mention of "code review" elsewhere in the command
        f'codex exec "$UNSET" # {REVIEW_PROMPT}',
    ],
)
def test_denies_codex_exec_whose_prompt_is_not_a_resolvable_review_request(tmp_path, command):
    assert_denied(run_hook(codex_foreground(tmp_path, command)))


# --- robustness ----------------------------------------------------------------------------------------------------


def test_malformed_transcript_lines_do_not_break_the_check(tmp_path):
    good = [bash_call("codex review"), bash_result()]
    odd = [
        "not json {codex",
        json.dumps([1, 2, "codex"]),
        json.dumps(
            {"message": {"content": [{"type": "tool_use", "name": "Bash", "id": ["x"], "input": "codex review"}]}}
        ),
        json.dumps({"message": {"content": [{"type": "tool_result", "tool_use_id": ["codex"], "is_error": True}]}}),
        json.dumps({"message": "codex tool_result", "type": "queue-operation", "content": 5}),
        json.dumps(bash_call("codex review", tool_id="toolu_9", timestamp=12345)),
    ]
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join([*odd, *(json.dumps(r) for r in good)]))
    assert run_hook(path) is None
    path.write_text("\n".join(odd))
    assert_denied(run_hook(path))


# --- pre-flight: an unprovable codex review is blocked before it runs, not at publish time ----------------------


@pytest.mark.parametrize(
    "command",
    [
        f'codex exec "{REVIEW_PROMPT}" | tail -40',
        "codex review --base main 2>&1 | tail -40",
        f'codex exec "{REVIEW_PROMPT}" | tee out.md',
        f'codex exec "{REVIEW_PROMPT}"; echo done',
        f'codex exec "{REVIEW_PROMPT}" || true',
        f'nohup codex exec "{REVIEW_PROMPT}" > /tmp/codex.log 2>&1 &',
    ],
)
def test_preflight_denies_codex_review_that_could_never_count(tmp_path, command):
    assert_denied(run_hook(transcript_rows(tmp_path), command))


@pytest.mark.parametrize(
    "command",
    [
        f'codex exec "{REVIEW_PROMPT}"',
        f'cd /work/wt && codex exec "{REVIEW_PROMPT}" > /tmp/codex.log 2>&1',
        f'set -o pipefail; codex exec "{REVIEW_PROMPT}" | tail -40',
        f'nohup codex exec -o /tmp/out.md "{REVIEW_PROMPT}" > /tmp/codex.log 2>&1 &',
        'codex exec "fix the failing test" | tail -5',  # not a review
        "codex --version | head -1",
        "ls | tail",
    ],
)
def test_preflight_allows_provable_or_unrelated_commands(tmp_path, command):
    assert run_hook(transcript_rows(tmp_path), command) is None


def test_preflight_allows_once_a_review_was_already_accepted(tmp_path):
    path = transcript_rows(tmp_path, bash_call("codex review"), bash_result())
    assert run_hook(path, "codex review | tail -40") is None


# --- sessions run in Codex ---------------------------------------------------------------------------------------


def codex_rollout(tmp_path: Path, *rows: dict) -> Path:
    meta = {"type": "session_meta", "payload": {"originator": "codex_exec"}}
    path = tmp_path / "rollout.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in [meta, *rows]))
    return path


def codex_command(command: str, exit_code: int = 0, started_ms: int = 1_000) -> dict:
    item = {
        "type": "CommandExecution",
        "command": ["/bin/bash", "-lc", command],
        "cwd": "file:///work/wt",
        "status": "completed",
        "exit_code": exit_code,
    }
    return {
        "type": "event_msg",
        "payload": {"type": "item_completed", "item": item, "started_at_ms": started_ms},
    }


def codex_skill_message(name: str, role: str = "user") -> dict:
    text = f"<skill>\n<name>{name}</name>\n<path>/x/SKILL.md</path>\n---\nname: x\n---\n</skill>"
    payload = {"type": "message", "role": role, "content": [{"type": "input_text", "text": text}]}
    return {"type": "response_item", "payload": payload}


@pytest.mark.parametrize("name", ["bms-code-review", "dev-workflow:bms-code-review", "code-review"])
def test_codex_allows_after_explicitly_invoked_review_skill(tmp_path, name):
    assert run_hook(codex_rollout(tmp_path, codex_skill_message(name))) is None


@pytest.mark.parametrize("name", ["bms-plan-review", "dev-workflow:design-review"])
def test_codex_denies_after_other_review_skill(tmp_path, name):
    assert_denied(run_hook(codex_rollout(tmp_path, codex_skill_message(name))))


def test_codex_denies_a_review_skill_text_in_a_non_user_message(tmp_path):
    assert_denied(run_hook(codex_rollout(tmp_path, codex_skill_message("bms-code-review", role="assistant"))))


def test_codex_allows_after_the_model_read_the_review_skill_file(tmp_path):
    cmd = "cat /home/u/.codex/plugins/cache/bmsuisse-skills/dev-workflow/local/skills/bms-code-review/SKILL.md"
    assert run_hook(codex_rollout(tmp_path, codex_command(cmd))) is None


def test_codex_denies_a_failed_read_of_the_review_skill_file(tmp_path):
    assert_denied(run_hook(codex_rollout(tmp_path, codex_command("cat skills/bms-code-review/SKILL.md", exit_code=1))))


def test_codex_allows_after_the_builtin_review_mode(tmp_path):
    row = {"type": "event_msg", "payload": {"type": "exited_review_mode"}}
    assert run_hook(codex_rollout(tmp_path, row)) is None


def test_codex_allows_after_a_finished_nested_codex_review(tmp_path):
    assert run_hook(codex_rollout(tmp_path, codex_command(f'codex exec -s read-only "{REVIEW_PROMPT}"'))) is None


def test_codex_denies_a_failed_nested_codex_review(tmp_path):
    cmd = f'codex exec -s read-only "{REVIEW_PROMPT}"'
    assert_denied(run_hook(codex_rollout(tmp_path, codex_command(cmd, exit_code=1))))


def test_codex_denies_a_nested_codex_review_whose_failure_the_exit_code_would_hide(tmp_path):
    assert_denied(run_hook(codex_rollout(tmp_path, codex_command(f'codex exec "{REVIEW_PROMPT}" | tee /tmp/o.md'))))


def test_codex_allows_backgrounded_nested_review_with_fresh_output_file(tmp_path):
    out = tmp_path / "out.md"
    out.write_text("findings")
    cmd = f'nohup codex exec -o {out} "{REVIEW_PROMPT}" > /dev/null 2>&1 &'
    assert run_hook(codex_rollout(tmp_path, codex_command(cmd, started_ms=1_000))) is None


def test_codex_denies_backgrounded_nested_review_without_output_file(tmp_path):
    cmd = f'nohup codex exec -o {tmp_path / "missing.md"} "{REVIEW_PROMPT}" > /dev/null 2>&1 &'
    assert_denied(run_hook(codex_rollout(tmp_path, codex_command(cmd))))


def test_codex_denies_without_any_review(tmp_path):
    assert_denied(run_hook(codex_rollout(tmp_path, codex_command("git status"))))


@pytest.mark.parametrize(
    "command",
    [
        "sed -n '1,200p' /x/dev-workflow/local/skills/bms-code-review/SKILL.md",
        "cd /x && head -50 skills/code-review/SKILL.md",
        "cat skills/bms-code-review/SKILL.md | head -20",
    ],
)
def test_codex_allows_common_ways_to_read_the_review_skill(tmp_path, command):
    assert run_hook(codex_rollout(tmp_path, codex_command(command))) is None


@pytest.mark.parametrize(
    "command",
    [
        "echo skills/bms-code-review/SKILL.md",
        "ls skills/bms-code-review/SKILL.md",
        "git commit -m 'read skills/bms-code-review/SKILL.md'",
    ],
)
def test_codex_denies_commands_that_only_mention_the_review_skill_file(tmp_path, command):
    assert_denied(run_hook(codex_rollout(tmp_path, codex_command(command))))


# --- promotion PRs (dev -> test -> main) need no review ----------------------------------------------------------


def git_repo_on(tmp_path: Path, branch: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i"],
        cwd=repo,
        check=True,
    )
    return repo


def fake_cli(tmp_path: Path, name: str, stdout: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / name
    script.write_text(f"#!/bin/sh\ncat <<'EOF'\n{stdout}\nEOF\n")
    script.chmod(0o755)
    return bin_dir


@pytest.mark.parametrize(
    "command",
    [
        "az repos pr create --source-branch dev --target-branch test --auto-complete true",
        "az repos pr create --source-branch refs/heads/test --target-branch main --auto-complete true",
        "az repos pr create --source-branch=main --target-branch=dev --auto-complete true",
        "gh pr create --head dev --base test",
        "bdt pr create --no-draft --target test -- --source-branch dev",
    ],
)
def test_promotion_pr_with_explicit_branches_needs_no_review(tmp_path, command):
    assert run_hook(transcript_with(tmp_path, None), command) is None


@pytest.mark.parametrize(
    "command",
    [
        "az repos pr create --source-branch feature/x --target-branch dev --auto-complete true",
        "az repos pr create --source-branch fix/x --target-branch main --auto-complete true",
        "gh pr create --head hotfix/x --base main",
        "gh pr create --head dev --base feature/x",
        "bdt pr create --no-draft --target main -- --source-branch fix/x",
    ],
)
def test_non_promotion_pr_with_explicit_branches_still_needs_review(tmp_path, command):
    assert_denied(run_hook(transcript_with(tmp_path, None), command))


def test_bdt_create_defaults_to_dev_target(tmp_path):
    transcript = transcript_with(tmp_path, None)
    assert_denied(run_hook(transcript, "bdt pr create --no-draft", cwd=git_repo_on(tmp_path, "feature-x")))


def test_bdt_create_from_test_branch_into_default_dev_target_is_a_promotion(tmp_path):
    # main -> dev merge-back: both ends are promotion branches
    repo = git_repo_on(tmp_path, "main")
    assert run_hook(transcript_with(tmp_path, None), "bdt pr create --no-draft", cwd=repo) is None


def test_bdt_create_from_dev_to_test_needs_no_review(tmp_path):
    repo = git_repo_on(tmp_path, "dev")
    assert run_hook(transcript_with(tmp_path, None), "bdt pr create --no-draft --target test", cwd=repo) is None


def test_bdt_create_from_feature_branch_to_test_still_needs_review(tmp_path):
    repo = git_repo_on(tmp_path, "feature-x")
    assert_denied(run_hook(transcript_with(tmp_path, None), "bdt pr create --no-draft --target test", cwd=repo))


def test_publish_looks_up_the_promotion_pr_via_gh(tmp_path):
    bin_dir = fake_cli(tmp_path, "gh", '{"headRefName": "dev", "baseRefName": "test"}')
    out = run_hook(transcript_with(tmp_path, None), "gh pr merge 7 --squash", path_prefix=bin_dir)
    assert out is None


def test_publish_of_a_feature_pr_found_via_gh_still_needs_review(tmp_path):
    bin_dir = fake_cli(tmp_path, "gh", '{"headRefName": "feature/x", "baseRefName": "dev"}')
    assert_denied(run_hook(transcript_with(tmp_path, None), "gh pr ready 7", path_prefix=bin_dir))


def test_az_update_looks_up_the_promotion_pr_via_az(tmp_path):
    bin_dir = fake_cli(tmp_path, "az", "refs/heads/test\nrefs/heads/main")
    out = run_hook(
        transcript_with(tmp_path, None), "az repos pr update --id 12 --status completed", path_prefix=bin_dir
    )
    assert out is None


def test_unresolvable_branches_fall_back_to_requiring_review(tmp_path):
    assert_denied(run_hook(transcript_with(tmp_path, None), "gh pr merge 7"))


@pytest.mark.parametrize(
    "command",
    [
        "gh pr create --head hotfix/x --base main; echo --head dev --base test",
        "cd ../other && bdt pr create --no-draft --target main",
        "gh pr merge 7 --repo org/other",
        "az repos pr update --id 12 --status completed --organization https://dev.azure.com/other",
        "gh pr merge --body dev 7 --merge",
        "gh pr create --head dev --base test && gh pr create --head hotfix/x --base main",
    ],
)
def test_ambiguous_or_foreign_context_never_counts_as_a_promotion(tmp_path, command):
    bin_dir = fake_cli(tmp_path, "gh", '{"headRefName": "dev", "baseRefName": "test"}')
    assert_denied(
        run_hook(transcript_with(tmp_path, None), command, cwd=git_repo_on(tmp_path, "dev"), path_prefix=bin_dir)
    )


def test_flags_of_other_commands_in_the_line_are_not_borrowed(tmp_path):
    bin_dir = fake_cli(tmp_path, "gh", '{"headRefName": "hotfix/x", "baseRefName": "main"}')
    command = "echo --head dev --base test && gh pr merge 7"
    assert_denied(run_hook(transcript_with(tmp_path, None), command, path_prefix=bin_dir))
