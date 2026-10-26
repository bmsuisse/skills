"""Tests for the init-app-stack translate_on_edit PostToolUse hook (uses a fake `just`, so no just install needed)."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "skills" / "init-app-stack" / "hooks" / "translate_on_edit.py"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "justfile").write_text("translate:\n    uv run bdt translate\n")
    (tmp_path / "translations.toml").write_text('[A]\nen = "a"\n')
    (tmp_path / "bin").mkdir()
    return tmp_path


def fake_just(root: Path, show_code: int = 0, run_code: int = 0, output: str = "") -> dict:
    """A `just` that records how it was called in calls.log; `--show` exits show_code, a recipe run run_code."""
    exe = root / "bin" / "just"
    exe.write_text(
        f"#!/bin/sh\necho \"$@\" >> '{root}/calls.log'\n"
        f'if [ "$1" = "--show" ]; then exit {show_code}; fi\necho \'{output}\'\nexit {run_code}\n'
    )
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return {**os.environ, "PATH": f"{root / 'bin'}:/usr/bin:/bin"}


def run_hook(file: Path, env: dict | None = None, project: Path | None = None) -> subprocess.CompletedProcess:
    """Run the hook as Claude Code does: CLAUDE_PROJECT_DIR is the project root (default: the file's directory's root)."""
    env = {**(env or os.environ), "CLAUDE_PROJECT_DIR": str(project or file.parent)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"file_path": str(file)}}),
        capture_output=True,
        text=True,
        env=env,
    )


def calls(root: Path) -> list[str]:
    log = root / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def test_runs_the_shared_recipe_when_translations_toml_is_edited(project):
    result = run_hook(project / "translations.toml", fake_just(project))
    assert result.returncode == 0
    assert calls(project) == ["--show translate", "translate"]


def test_uses_the_project_justfile_for_a_nested_translations_toml(project):
    nested = project / "akeneo_editor"
    nested.mkdir()
    (nested / "translations.toml").write_text('[A]\nen = "a"\n')
    result = run_hook(nested / "translations.toml", fake_just(project), project=project)
    assert result.returncode == 0
    assert calls(project) == ["--show translate", "translate"]


def test_failure_is_fed_back_with_exit_2(project):
    result = run_hook(project / "translations.toml", fake_just(project, run_code=1, output="missing key FOO"))
    assert result.returncode == 2
    assert "missing key FOO" in result.stderr


def test_ignores_other_files(project):
    other = project / "README.md"
    other.write_text("x")
    assert run_hook(other, fake_just(project)).returncode == 0
    assert calls(project) == []


def test_noop_without_a_translate_recipe(project):
    result = run_hook(project / "translations.toml", fake_just(project, show_code=1))
    assert result.returncode == 0
    assert calls(project) == ["--show translate"]


def test_noop_without_just(project):
    env = {**os.environ, "PATH": str(project / "bin")}
    assert run_hook(project / "translations.toml", env).returncode == 0


def test_noop_without_a_justfile(tmp_path):
    (tmp_path / "translations.toml").write_text('[A]\nen = "a"\n')
    (tmp_path / "bin").mkdir()
    assert run_hook(tmp_path / "translations.toml", fake_just(tmp_path)).returncode == 0
    assert calls(tmp_path) == []


def test_ignores_translations_toml_outside_the_project(project, tmp_path_factory):
    vendored = tmp_path_factory.mktemp("vendored")
    (vendored / "justfile").write_text("translate:\n    echo pwned\n")
    (vendored / "translations.toml").write_text('[A]\nen = "a"\n')
    result = run_hook(vendored / "translations.toml", fake_just(project), project=project)
    assert result.returncode == 0
    assert calls(project) == []


def test_ignores_a_justfile_that_is_not_at_the_project_root(project):
    sub = project / "vendor"
    sub.mkdir()
    (sub / "justfile").write_text("translate:\n    echo pwned\n")
    (sub / "translations.toml").write_text('[A]\nen = "a"\n')
    (project / "justfile").unlink()
    result = run_hook(sub / "translations.toml", fake_just(project), project=project)
    assert result.returncode == 0
    assert calls(project) == []
