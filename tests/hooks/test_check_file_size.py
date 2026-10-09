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


def test_warns_between_600_and_limit(tmp_path):
    r = run(make(tmp_path, "mid.py", 700))
    assert r.returncode == 0 and "Warning" in r.stdout


def test_generated_and_unknown_files_are_skipped(tmp_path):
    (tmp_path / "generated").mkdir()
    assert run(make(tmp_path / "generated", "api.py", 5000)).returncode == 0
    assert run(make(tmp_path, "data.csv", 5000)).returncode == 0
