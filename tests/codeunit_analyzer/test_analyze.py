
from pathlib import Path
from unittest.mock import patch

from analyze import _analyze_codeunit_for_scan, scan_all_bottlenecks


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


def test_analyze_codeunit_for_scan_returns_list(tmp_path: Path):
    file_info = make_file_info(tmp_path)
    with patch("analyze.analyze_codeunit", return_value={"object": {}, "bottlenecks": []}):
        result = _analyze_codeunit_for_scan(file_info, {})
    assert isinstance(result, list)


def test_analyze_codeunit_for_scan_swallows_errors(tmp_path: Path):
    bad_info = {"path": tmp_path / "ghost.c-al", "name": "ghost.c-al"}
    result = _analyze_codeunit_for_scan(bad_info, {})
    assert result == []


def test_scan_all_bottlenecks_returns_list(tmp_path: Path):
    with (
        patch("analyze.list_codeunits", return_value=[]),
        patch("analyze.TableMetadataLoader.load_metadata", return_value={}),
    ):
        result = scan_all_bottlenecks()
    assert isinstance(result, list)
