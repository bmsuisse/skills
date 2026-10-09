"""Tests for clean-code's check_file_size gate."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "clean-code" / "scripts" / "check_file_size.py"


def run(*files: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, files)], capture_output=True, text=True)


def make(tmp_path: Path, name: str, lines: int) -> Path:
    f = tmp_path / name
    f.write_text("x = 1\n" * lines)
    return f


def test_over_limit_fails_under_limit_passes(tmp_path):
    assert run(make(tmp_path, "big.sh", 101)).returncode == 1
    assert run(make(tmp_path, "ok.sh", 100)).returncode == 0


def test_tests_get_more_room(tmp_path):
    assert run(make(tmp_path, "test_big.py", 1500)).returncode == 0  # 1200 * 1.5 = 1800
    assert run(make(tmp_path, "test_huge.py", 1801)).returncode == 1


def test_warns_at_75_percent_of_each_limit(tmp_path):
    for name, lines in [("mid.py", 950), ("mid.ts", 460), ("mid.md", 380), ("mid.sh", 80)]:
        r = run(make(tmp_path, name, lines))
        assert r.returncode == 0 and "Warning" in r.stdout, name
    assert run(make(tmp_path, "small.ts", 100)).stdout == ""


def test_other_test_conventions_get_the_allowance(tmp_path):
    (tmp_path / "tests").mkdir()
    for f in [tmp_path / "conftest.py", tmp_path / "foo_test.py", tmp_path / "tests" / "helpers.py", tmp_path / "a.spec.ts"]:
        limit = 600 if f.suffix == ".ts" else 1200
        assert run(make(f.parent, f.name, int(limit * 1.2))).returncode == 0, f.name


def test_generated_and_unknown_files_are_skipped(tmp_path):
    (tmp_path / "generated").mkdir()
    assert run(make(tmp_path / "generated", "api.py", 5000)).returncode == 0
    assert run(make(tmp_path, "data.csv", 5000)).returncode == 0


def test_exact_test_limit_and_lock_and_generated_name_skips(tmp_path):
    assert run(make(tmp_path, "test_edge.py", 1800)).returncode == 0
    assert run(make(tmp_path, "uv.lock", 9000)).returncode == 0
    assert run(make(tmp_path, "api.generated.ts", 9000)).returncode == 0


def test_absolute_paths_under_a_generated_parent_are_still_checked(tmp_path):
    parent = tmp_path / "generated" / "src"
    parent.mkdir(parents=True)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(make(parent, "big.sh", 101))], capture_output=True, text=True, cwd=parent
    )
    assert r.returncode == 1


def test_missing_and_undecodable_files_do_not_crash(tmp_path):
    bad = tmp_path / "latin.py"
    bad.write_bytes(b"x = '\xe9'\n" * 5)
    r = run(bad, tmp_path / "gone.py")
    assert r.returncode == 0 and "not checked" in r.stdout
