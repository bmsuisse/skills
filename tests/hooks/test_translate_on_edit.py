"""Tests for the dev-workflow translate-on-edit PostToolUse hook (uses a fake `uv`, so no uv/bdt install needed)."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "translate-on-edit.py"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.bdt.translate]\noutput = ["frontend/src/locales"]\n')
    (tmp_path / "translations.toml").write_text('[A]\nen = "a"\n')
    (tmp_path / "bin").mkdir()
    return tmp_path


def fake_uv(root: Path, run_code: int = 0, output: str = "") -> dict:
    """A `uv` that records how it was called (and from which directory) in calls.log."""
    exe = root / "bin" / "uv"
    exe.write_text(f"#!/bin/sh\necho \"$PWD: $@\" >> '{root}/calls.log'\necho '{output}'\nexit {run_code}\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return {**os.environ, "PATH": f"{root / 'bin'}:/usr/bin:/bin"}


def run_hook(
    file: Path, env: dict | None = None, project: Path | None = None, payload: dict | None = None
) -> subprocess.CompletedProcess:
    """Run the hook as Claude Code does: CLAUDE_PROJECT_DIR is the project root (default: the file's directory)."""
    env = {**(env or os.environ), "CLAUDE_PROJECT_DIR": str(project or file.parent)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload or {"tool_input": {"file_path": str(file)}}),
        capture_output=True,
        text=True,
        env=env,
    )


def calls(root: Path) -> list[str]:
    log = root / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def test_runs_bdt_translate_in_the_project_root_when_translations_toml_is_edited(project):
    result = run_hook(project / "translations.toml", fake_uv(project))
    assert result.returncode == 0
    assert calls(project) == [f"{project.resolve()}: run bdt translate"]


def test_runs_from_the_project_root_for_a_nested_translations_toml(project):
    nested = project / "akeneo_editor"
    nested.mkdir()
    (nested / "translations.toml").write_text('[A]\nen = "a"\n')
    result = run_hook(nested / "translations.toml", fake_uv(project), project=project)
    assert result.returncode == 0
    assert calls(project) == [f"{project.resolve()}: run bdt translate"]


def test_failure_is_fed_back_with_exit_2(project):
    result = run_hook(project / "translations.toml", fake_uv(project, run_code=1, output="missing key FOO"))
    assert result.returncode == 2
    assert "missing key FOO" in result.stderr


def test_ignores_other_files(project):
    other = project / "README.md"
    other.write_text("x")
    assert run_hook(other, fake_uv(project)).returncode == 0
    assert calls(project) == []


def test_noop_without_bdt_translate_config(project):
    (project / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert run_hook(project / "translations.toml", fake_uv(project)).returncode == 0
    assert calls(project) == []


def test_noop_without_a_pyproject(project):
    (project / "pyproject.toml").unlink()
    assert run_hook(project / "translations.toml", fake_uv(project)).returncode == 0
    assert calls(project) == []


def test_noop_without_uv(project):
    env = {**os.environ, "PATH": str(project / "bin")}
    assert run_hook(project / "translations.toml", env).returncode == 0


def test_ignores_translations_toml_outside_the_project(project, tmp_path_factory):
    vendored = tmp_path_factory.mktemp("vendored")
    (vendored / "pyproject.toml").write_text("[tool.bdt.translate]\n")
    (vendored / "translations.toml").write_text('[A]\nen = "a"\n')
    result = run_hook(vendored / "translations.toml", fake_uv(project), project=project)
    assert result.returncode == 0
    assert calls(project) == []


def test_edit_in_a_worktree_regenerates_that_worktree_not_the_main_checkout(project):
    worktree = project / ".worktrees" / "task"
    worktree.mkdir(parents=True)
    (worktree / "pyproject.toml").write_text("[tool.bdt.translate]\n")
    (worktree / "translations.toml").write_text('[A]\nen = "a"\n')
    result = run_hook(worktree / "translations.toml", fake_uv(project), project=project)
    assert result.returncode == 0
    assert calls(project) == [f"{worktree.resolve()}: run bdt translate"]


def test_codex_apply_patch_headers_trigger_translation_relative_to_cwd(project):
    patch = (
        "*** Begin Patch\n*** Update File: translations.toml\n@@\n-x\n+y\n*** Update File: README.md\n*** End Patch\n"
    )
    payload = {"tool_name": "apply_patch", "cwd": str(project), "tool_input": {"command": patch}}
    result = run_hook(project / "translations.toml", fake_uv(project), project=project, payload=payload)
    assert result.returncode == 0
    assert calls(project) == [f"{project.resolve()}: run bdt translate"]


def test_codex_apply_patch_without_translations_toml_is_ignored(project):
    patch = "*** Begin Patch\n*** Update File: README.md\n@@\n-x\n+y\n*** End Patch\n"
    payload = {"tool_name": "apply_patch", "cwd": str(project), "tool_input": {"command": patch}}
    result = run_hook(project / "translations.toml", fake_uv(project), project=project, payload=payload)
    assert result.returncode == 0
    assert calls(project) == []
