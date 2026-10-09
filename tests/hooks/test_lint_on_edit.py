"""Tests for the clean-code lint_on_edit PostToolUse hook (uses a fake ruff, so no ruff install needed)."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "skills" / "clean-code" / "hooks" / "lint_on_edit.py"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 120\n")
    (tmp_path / "bin").mkdir()
    return tmp_path


def fake_ruff(root: Path, exit_code: int, output: str) -> dict:
    exe = root / "bin" / "ruff"
    exe.write_text(f"#!/bin/sh\necho '{output}'\nexit {exit_code}\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return {**os.environ, "PATH": f"{root / 'bin'}:/usr/bin:/bin"}


def run_hook(file: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"file_path": str(file)}}),
        capture_output=True,
        text=True,
        env=env,
    )


def test_remaining_violations_are_fed_back_with_exit_2(project):
    f = project / "a.py"
    f.write_text("import os\n")
    r = run_hook(f, fake_ruff(project, 1, "a.py:1:8: F401 unused import"))
    assert r.returncode == 2
    assert "F401" in r.stderr


def test_clean_file_is_silent(project):
    f = project / "a.py"
    f.write_text("x = 1\n")
    r = run_hook(f, fake_ruff(project, 0, ""))
    assert (r.returncode, r.stderr) == (0, "")


def test_no_ruff_config_is_a_noop(project):
    (project / "pyproject.toml").write_text("[project]\nname='x'\n")
    f = project / "a.py"
    f.write_text("import os\n")
    assert run_hook(f, fake_ruff(project, 1, "boom")).returncode == 0


def test_other_file_types_and_missing_files_are_noops(project):
    env = fake_ruff(project, 1, "boom")
    md = project / "README.md"
    md.write_text("hi")
    assert run_hook(md, env).returncode == 0
    assert run_hook(project / "gone.py", env).returncode == 0


def test_linter_failure_never_blocks(project):
    f = project / "a.py"
    f.write_text("x = 1\n")
    r = run_hook(f, fake_ruff(project, 2, "error: invalid config"))
    assert (r.returncode, r.stderr) == (0, "")
