"""Tests for the ban-handwired-ci-watch PreToolUse hook."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "ban-handwired-ci-watch.py"

BUILD_API = "https://dev.azure.com/bmeurope/P/_apis/build/builds"
PR_API = "https://dev.azure.com/bmeurope/P/_apis/git/repositories/R/pullrequests"


def run_hook(command: str, tool_name: str = "Bash") -> dict | None:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else None


def is_denied(response: dict | None) -> bool:
    return response is not None and response["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "command",
    [
        # polling loops around a PR or CI query
        "while true; do az repos pr show --id 1 --query status; sleep 30; done",
        "until [ \"$(az repos pr show --id 1 --query status -o tsv)\" = completed ]; do sleep 20; done",
        "for i in 1 2 3; do az repos pr list --status active; sleep 60; done",
        f'while true; do curl -s -u ":$PAT" "{PR_API}/12?api-version=7.1"; sleep 30; done',
        "while sleep 30; do gh pr view 3 --json state; done",
        "az repos pr show --id 1 && sleep 30 && az repos pr show --id 1",
        "watch -n 30 az repos pr show --id 1",
        "timeout 600 bash -c 'while true; do az repos pr show --id 1; sleep 5; done'",
        "python3 - <<'EOF'\nimport subprocess, time\nwhile True:\n    subprocess.run(['az', 'repos', 'pr', 'show', '--id', '1'])\n    time.sleep(30)\nEOF",
        # CI status queries, polled or not
        "az pipelines runs list --branch refs/pull/1/merge",
        "az pipelines runs show --id 12 --query result",
        "az pipelines build list --top 3",
        "gh run watch 123",
        "gh run list --branch x",
        "gh pr checks 4",
        f'curl -s -u ":$PAT" "{BUILD_API}/123/timeline?api-version=7.1"',
        f'curl -s "{BUILD_API}?branchName=refs/pull/1/merge" | python3 -c "import sys,json; print(json.load(sys.stdin))"',
        f"source ~/.devops.env; B='{BUILD_API}'; for id in 1 2; do curl -s \"$B/$id/timeline\"; done",
        "cd repo && AZURE_DEVOPS_EXT_PAT=x az pipelines runs list",
        "az pipelines runs \\\nlist",
        "env -i az pipelines runs list",
        "if true; then az pipelines runs show --id 1; fi",
        "eval 'az pipelines runs list'",
    ],
)
def test_denies_handwired_watch(command: str) -> None:
    response = run_hook(command)
    assert is_denied(response)
    assert "bdt pr status --wait" in response["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        # single PR reads: labels, threads, attachments have no bdt command
        "az repos pr show --id 1",
        "az repos pr list --status active",
        f'curl -s -u ":$PAT" "{PR_API}/12/labels?api-version=7.1"',
        f'curl -s -u ":$PAT" "{PR_API}/12/threads?api-version=7.1"',
        "gh pr view 3 --json body",
        # build logs and artifacts, not status
        f'curl -s -u ":$PAT" "{BUILD_API}/123/logs/5?api-version=7.1"',
        f'curl -s -u ":$PAT" "{BUILD_API}/123/artifacts?api-version=7.1"',
        # triggering and the rest of the az pr surface
        "az pipelines run --branch x --id 3",
        "az repos pr update --id 1 --title x",
        "az repos pr create --title x",
        # an assignment the call does not use
        "B=_apis/build/builds; gh pr view 123",
        # polling something else
        "while true; do curl -s localhost:8000/health && break; sleep 2; done",
        "sleep 30",
        # bdt itself
        "bdt pr status --wait --timeout 540",
        "bdt pr info --pr-id 3",
        "bdt pr create --title x -- --description 'replaces az repos pr show and az pipelines runs list'",
        # only mentioned, not run
        'echo "az pipelines runs list"',
        "grep -r 'az repos pr show; sleep' docs",
        "git commit -m 'drop az pipelines runs list loop'",
        "cat > notes.md <<'EOF'\nwhile true; do az pipelines runs list; sleep 30; done\nEOF",
    ],
)
def test_allows_other_commands(command: str) -> None:
    assert run_hook(command) is None


def test_ignores_non_bash_tools() -> None:
    assert run_hook("az pipelines runs list", tool_name="Write") is None


def test_hints_install_when_bdt_is_missing(tmp_path: Path) -> None:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "az pipelines runs list"}})
    env = {"PATH": str(tmp_path), "HOME": str(tmp_path)}
    result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, timeout=10, env=env)
    assert "uv tool install bmsdna-devtools" in json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
