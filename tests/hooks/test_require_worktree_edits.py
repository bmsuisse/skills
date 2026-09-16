"""Tests for the require-worktree-edits PreToolUse hook."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "require-worktree-edits.py"


@pytest.fixture
def repo_dir():
    # /tmp itself is an always-allowed path prefix (see ALLOWED_PREFIX), so the
    # path-based gate tests need a directory outside it to actually exercise
    # the git-based checks.
    with tempfile.TemporaryDirectory(dir="/var/tmp") as d:
        yield Path(d)


def run_hook(file_path: str, cwd: Path) -> dict | None:
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
    )
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def is_denied(response: dict | None) -> bool:
    if response is None:
        return False
    return response.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def init_git_repo(path: Path, with_remote: bool) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    if with_remote:
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.invalid/repo.git"],
            cwd=path,
            check=True,
        )


# ---------------------------------------------------------------------------
# Always-allowed path patterns
# ---------------------------------------------------------------------------


def test_allows_worktree_path(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    assert not is_denied(run_hook(str(tmp_path / "worktree-foo" / "bar.py"), tmp_path))


def test_allows_dot_claude_path(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    assert not is_denied(run_hook(str(tmp_path / ".claude" / "settings.json"), tmp_path))


def test_allows_tmp_path(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    assert not is_denied(run_hook("/tmp/scratch/foo.py", tmp_path))


# ---------------------------------------------------------------------------
# Windows / WSL temp directories
# ---------------------------------------------------------------------------


def test_allows_windows_temp_forward_slash(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    assert not is_denied(run_hook("C:/Users/foo/AppData/Local/Temp/bar.txt", tmp_path))


def test_allows_windows_temp_backslash(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    assert not is_denied(run_hook(r"C:\Users\foo\AppData\Local\Temp\bar.txt", tmp_path))


def test_allows_windows_system_temp(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    assert not is_denied(run_hook(r"C:\Windows\Temp\bar.txt", tmp_path))


def test_allows_wsl_mounted_windows_temp(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    assert not is_denied(run_hook("/mnt/c/Users/foo/AppData/Local/Temp/bar.txt", tmp_path))


# ---------------------------------------------------------------------------
# Path-based exemptions (resolved from the target file, not the process cwd)
# ---------------------------------------------------------------------------


def test_blocks_by_default_in_git_repo_with_remote(repo_dir: Path) -> None:
    init_git_repo(repo_dir, with_remote=True)
    assert is_denied(run_hook(str(repo_dir / "foo.py"), repo_dir))


def test_allows_when_target_dir_is_not_a_git_repo(repo_dir: Path) -> None:
    assert not is_denied(run_hook(str(repo_dir / "foo.py"), repo_dir))


def test_allows_when_target_repo_has_no_remote(repo_dir: Path) -> None:
    init_git_repo(repo_dir, with_remote=False)
    assert not is_denied(run_hook(str(repo_dir / "foo.py"), repo_dir))


def test_allows_new_file_in_not_yet_existing_subdir(repo_dir: Path) -> None:
    # Write can target a file whose parent dir doesn't exist yet; resolution
    # should walk up to the nearest existing ancestor (repo_dir itself).
    assert not is_denied(run_hook(str(repo_dir / "new_subdir" / "foo.py"), repo_dir))


def test_uses_target_path_repo_not_process_cwd(repo_dir: Path) -> None:
    # cwd is a plain non-git scratch dir, but the edited file lives in a
    # separate git+remote checkout - the gate must key off the target path's
    # repo, not the hook process's cwd, or an unrelated cwd could bypass it.
    # Both dirs must live outside /tmp, since /tmp itself is always-allowed.
    with tempfile.TemporaryDirectory(dir="/var/tmp") as protected:
        protected_repo = Path(protected)
        init_git_repo(protected_repo, with_remote=True)
        assert is_denied(run_hook(str(protected_repo / "foo.py"), repo_dir))


def test_target_path_with_no_remote_allowed_even_from_protected_cwd(repo_dir: Path) -> None:
    # Inverse: cwd is a protected git+remote checkout, but the edited file
    # lives in an unrelated no-remote repo - that edit should still be allowed.
    init_git_repo(repo_dir, with_remote=True)
    with tempfile.TemporaryDirectory(dir="/var/tmp") as no_remote:
        no_remote_repo = Path(no_remote)
        init_git_repo(no_remote_repo, with_remote=False)
        assert not is_denied(run_hook(str(no_remote_repo / "foo.py"), repo_dir))


def test_fails_closed_on_unrecognized_git_error(repo_dir: Path) -> None:
    # A git failure that isn't unambiguously "not a git repository" (e.g. a
    # corrupt config) must not be treated as an exemption.
    init_git_repo(repo_dir, with_remote=True)
    (repo_dir / ".git" / "config").write_text("[bad syntax")
    assert is_denied(run_hook(str(repo_dir / "foo.py"), repo_dir))


def test_no_op_when_no_file_path_given(tmp_path: Path) -> None:
    init_git_repo(tmp_path, with_remote=True)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {}}),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=10,
    )
    assert result.stdout.strip() == ""
