"""Tests for runner.py."""
import sys
from pathlib import Path

import pytest
from runner import ensure_dir, get_python_version, read_file, stem, write_output


def test_get_python_version():
    version = get_python_version()
    assert "Python" in version or version == ""


def test_read_write_roundtrip(tmp_path):
    src = tmp_path / "input.txt"
    src.write_text("line1\nline2\nline3\n", encoding="utf-8")
    lines = read_file(str(src))
    assert len(lines) == 3

    dst = tmp_path / "output.txt"
    write_output(str(dst), lines)
    assert dst.exists()


def test_ensure_dir_creates(tmp_path):
    new_dir = str(tmp_path / "sub" / "deep")
    result = ensure_dir(new_dir)
    assert Path(result).is_dir()


def test_ensure_dir_idempotent(tmp_path):
    # Calling twice must not raise
    d = str(tmp_path / "mydir")
    ensure_dir(d)
    ensure_dir(d)
    assert Path(d).is_dir()


def test_stem_basic():
    assert stem("myfile.py") == "myfile"
    assert stem("/some/path/module.tar.gz") == "module.tar"


def test_run_linter_returns_int(tmp_path):
    from runner import run_linter
    dummy = tmp_path / "ok.py"
    dummy.write_text("x = 1\n", encoding="utf-8")
    result = run_linter(str(dummy))
    assert isinstance(result, int)
