"""Tests for scan flow in analyze.py — specifically that _parse_codeunit_full
uses the pre-resolved path and does not re-scan the filesystem."""

from pathlib import Path
from unittest.mock import patch

from analyze import _parse_codeunit_full, scan_all_bottlenecks


CAL_CONTENT = """\
MyProc()
BEGIN
  SomeTable.FINDSET;
END;
"""


def make_file_info(tmp_path: Path, filename: str = "cu1.c-al", content: str = CAL_CONTENT) -> dict:
    f = tmp_path / filename
    f.write_text(content, encoding="utf-8")
    return {"path": f, "name": filename, "object_name": "Test CU", "object_id": 1}


def test_parse_codeunit_full_uses_path_directly(tmp_path: Path):
    """_parse_codeunit_full should parse successfully using file_info['path']
    without calling find_codeunit_files."""
    file_info = make_file_info(tmp_path)

    with patch("analyze.find_codeunit_files") as mock_find:
        result = _parse_codeunit_full(file_info, {})

    # find_codeunit_files must never be called — that was the O(N²) bug
    mock_find.assert_not_called()
    assert result is not None
    assert result["file"] == "cu1.c-al"
    assert "object" in result
    assert "bottlenecks" in result


def test_parse_codeunit_full_missing_file_returns_result_with_warning(tmp_path: Path):
    """Parser is lenient about missing files — returns a result with warnings rather than crashing."""
    bad_info = {"path": tmp_path / "nonexistent.c-al", "name": "nonexistent.c-al"}
    result = _parse_codeunit_full(bad_info, {})
    assert result is not None
    assert result["file"] == "nonexistent.c-al"
    assert any("c-al" in w.lower() or "not found" in w.lower() for w in result["object"]["warnings"])


def test_scan_all_bottlenecks_does_not_rescan_filesystem(tmp_path: Path):
    """scan_all_bottlenecks should only call find_codeunit_files once
    (inside list_codeunits), not once per file."""
    files = [make_file_info(tmp_path, f"cu{i}.c-al") for i in range(5)]

    with patch("analyze.find_codeunit_files") as mock_find:
        # Pass pre-built file list so list_codeunits isn't called at all
        scan_all_bottlenecks(files=files)

    mock_find.assert_not_called()


def test_scan_returns_list(tmp_path: Path):
    files = [make_file_info(tmp_path, "cu1.c-al")]
    result = scan_all_bottlenecks(files=files)
    assert isinstance(result, list)
