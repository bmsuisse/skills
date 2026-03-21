"""Tests for databricks-cli scripts/run.py — pure unit tests (no cluster needed)."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "databricks-cli" / "scripts"))
import run


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file, explicit, expected",
    [
        (None, "python", "python"),
        (None, "SQL", "sql"),
        (None, "R", "r"),
        (Path("script.py"), None, "python"),
        (Path("query.sql"), None, "sql"),
        (Path("analysis.r"), None, "r"),
        (Path("app.scala"), None, "scala"),
        (Path("data.csv"), None, "python"),  # unknown ext → python default
        (None, None, "python"),  # no file, no explicit → python
        (Path("query.sql"), "python", "python"),  # explicit overrides file ext
    ],
)
def test_detect_language(file: Path | None, explicit: str | None, expected: str) -> None:
    assert run.detect_language(file, explicit) == expected


# ---------------------------------------------------------------------------
# print_result
# ---------------------------------------------------------------------------


def test_print_result_success_text(capsys: pytest.CaptureFixture[str]) -> None:
    resp = {"results": {"resultType": "text", "data": "hello world"}}
    exit_code = run.print_result(resp)
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "hello world"


def test_print_result_error(capsys: pytest.CaptureFixture[str]) -> None:
    resp = {
        "results": {
            "resultType": "error",
            "cause": "NameError: name 'foo' is not defined",
            "summary": "Traceback ...\nNameError: name 'foo' is not defined",
        }
    }
    exit_code = run.print_result(resp)
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "NameError" in err
    assert "[FAILED]" in err


def test_print_result_no_output(capsys: pytest.CaptureFixture[str]) -> None:
    resp = {"results": {"resultType": "text"}}
    exit_code = run.print_result(resp)
    assert exit_code == 0
    assert "[no output]" in capsys.readouterr().out


def test_print_result_empty_results(capsys: pytest.CaptureFixture[str]) -> None:
    resp = {"results": {}}
    exit_code = run.print_result(resp)
    assert exit_code == 0


# ---------------------------------------------------------------------------
# _cli (mocked subprocess)
# ---------------------------------------------------------------------------


def test_cli_success() -> None:
    fake_result = type("R", (), {"returncode": 0, "stdout": '{"id": "abc123"}', "stderr": ""})()
    with patch("run.subprocess.run", return_value=fake_result) as mock_run:
        result = run._cli("premium", "post", "/api/1.2/contexts/create", {"clusterId": "c1"})
        assert result == {"id": "abc123"}
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "databricks"
        assert "--profile" in cmd
        assert "premium" in cmd


def test_cli_failure() -> None:
    fake_result = type("R", (), {"returncode": 1, "stdout": "", "stderr": "auth failed"})()
    with patch("run.subprocess.run", return_value=fake_result):
        with pytest.raises(SystemExit) as exc_info:
            run._cli("bad_profile", "get", "/api/1.2/contexts/status", {})
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# ARGS injection
# ---------------------------------------------------------------------------


def test_args_injection_prepends_dict(tmp_path: Path) -> None:
    script = tmp_path / "test_script.py"
    script.write_text('print(ARGS["key"])', encoding="utf-8")

    args_json = '{"key": "value"}'
    code = script.read_text(encoding="utf-8")
    code = f"ARGS = {args_json}\n{code}"

    assert code.startswith("ARGS = ")
    assert '"key": "value"' in code
    assert 'print(ARGS["key"])' in code


def test_args_validation_rejects_bad_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        json.loads("not valid json")
