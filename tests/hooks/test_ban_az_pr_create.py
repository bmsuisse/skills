"""Tests for the ban-az-pr-create PreToolUse hook."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "ban-az-pr-create.py"


def run_hook(command: str, tool_name: str = "Bash") -> dict | None:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, timeout=10)
    return json.loads(result.stdout) if result.stdout.strip() else None


def is_denied(response: dict | None) -> bool:
    return response is not None and response["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "az repos pr create --title x",
        "az repos pr create --draft true --source-branch b",
        "cd repo && az repos pr create --title x",
        "AZURE_DEVOPS_EXT_PAT=x az repos pr create",
        "git push; az repos pr create",
    ],
)
def test_denies_az_pr_create(command: str) -> None:
    response = run_hook(command)
    assert is_denied(response)
    assert "bdt pr create" in response["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        "az repos pr show --id 1",
        "az repos pr update --id 1 --title x",
        "az repos pr list",
        "bdt pr create --title x",
        "gh pr create --draft",
        'echo "az repos pr create"',
        "grep -r 'az repos pr create' docs",
    ],
)
def test_allows_other_commands(command: str) -> None:
    assert run_hook(command) is None


def test_ignores_non_bash_tools() -> None:
    assert run_hook("az repos pr create", tool_name="Write") is None
