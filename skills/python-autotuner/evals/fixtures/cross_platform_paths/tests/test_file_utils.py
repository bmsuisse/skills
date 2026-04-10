"""Tests for file_utils.py — platform-neutral test data."""
import os
import tempfile
from pathlib import Path

import pytest
from file_utils import (
    find_python_files,
    get_extension,
    join_paths,
    read_config,
    write_report,
)


@pytest.fixture()
def tmp_tree(tmp_path):
    """Create a small directory tree with .py files."""
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("y = 2")
    (tmp_path / "sub" / "c.txt").write_text("not python")
    return tmp_path


def test_find_python_files(tmp_tree):
    found = find_python_files(str(tmp_tree))
    stems = {Path(f).name for f in found}
    assert stems == {"a.py", "b.py"}


def test_find_python_files_excludes_non_py(tmp_tree):
    found = find_python_files(str(tmp_tree))
    assert not any(f.endswith(".txt") for f in found)


def test_read_config(tmp_path):
    cfg = tmp_path / "config.txt"
    cfg.write_text("key=value\nfoo=bar\n", encoding="utf-8")
    lines = read_config(str(cfg))
    assert lines == ["key=value", "foo=bar"]


def test_write_report(tmp_path):
    data = {"status": "ok", "count": 42}
    path = write_report(data, str(tmp_path))
    content = Path(path).read_text(encoding="utf-8")
    assert "status: ok" in content
    assert "count: 42" in content


def test_join_paths_basic():
    result = join_paths("a", "b", "c")
    # Normalise separators for cross-platform comparison
    assert result.replace("\\", "/") == "a/b/c"


def test_get_extension():
    assert get_extension("myfile.py") == ".py"
    assert get_extension("archive.tar.gz") == ".gz"
    assert get_extension("no_ext") == ""
