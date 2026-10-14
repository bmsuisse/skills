"""Tests for the gate-pr-publish PreToolUse hook."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "gate-pr-publish.py"


def run_hook(transcript: Path) -> dict | None:
    payload = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "bdt pr publish"},
            "transcript_path": str(transcript),
        }
    )
    result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, timeout=10)
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
        "codex review",
        "codex review --base main",
        "codex exec review --uncommitted",
        f'/usr/local/bin/codex exec "{REVIEW_PROMPT}" | tail -40',
        f'nohup codex exec "{REVIEW_PROMPT}"',
        f'timeout 900 env CODEX_HOME=/x codex exec "{REVIEW_PROMPT}"',
        f"bash -c 'codex exec \"{REVIEW_PROMPT}\"'",
        f'echo starting; codex exec -m gpt-5 "{REVIEW_PROMPT}"; echo done',
        "echo 'please do a code review' | codex exec -",
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


def background_start(tmp_path: Path, out: Path | None, timestamp: str | None = None) -> Path:
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
