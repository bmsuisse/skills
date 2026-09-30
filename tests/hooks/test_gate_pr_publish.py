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


@pytest.mark.parametrize("skill", ["code-review", "bms-code-review", "plugin:code-review", "dev-workflow:bms-code-review"])
def test_allows_after_review(tmp_path, skill):
    assert run_hook(transcript_with(tmp_path, skill)) is None


@pytest.mark.parametrize("skill", [None, "bms-plan-review", "design-review"])
def test_denies_without_review(tmp_path, skill):
    out = run_hook(transcript_with(tmp_path, skill))
    assert out is not None
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
