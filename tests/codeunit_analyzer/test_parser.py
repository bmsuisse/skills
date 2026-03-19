"""Tests for CodeunitParser (parser.py).

C-AL format notes:
  - Procedure signature must be at column 0 (no leading whitespace).
  - Body must be wrapped in BEGIN / END; blocks.
  - Body lines must be indented (at least one space/tab) and end with ';'.
"""

import textwrap
from pathlib import Path

from scripts.parser import CodeunitParser


def make_cal(tmp_path: Path, cal_text: str, cs_text: str | None = None) -> CodeunitParser:
    """Write a .c-al file (and optional .cs) then return the parser."""
    cal_file = tmp_path / "cu.c-al"
    cal_file.write_text(textwrap.dedent(cal_text).strip(), encoding="utf-8")
    if cs_text is not None:
        (tmp_path / "cu.cs").write_text(textwrap.dedent(cs_text).strip(), encoding="utf-8")
    return CodeunitParser(cal_file)


# Convenience: one-liner body
def proc(name: str, *body_lines: str) -> str:
    body = "\n".join(f"  {line}" for line in body_lines)
    return f"{name}()\nBEGIN\n{body}\nEND;\n"


# ---------------------------------------------------------------------------
# Procedure detection
# ---------------------------------------------------------------------------


def test_single_procedure_detected(tmp_path: Path):
    report = make_cal(tmp_path, proc("MyProc", "x := 1;")).parse()
    assert "MyProc" in report["procedures"]


def test_multiple_procedures_detected(tmp_path: Path):
    report = make_cal(tmp_path, proc("ProcA", "x := 1;") + "\n" + proc("ProcB", "y := 2;")).parse()
    assert "ProcA" in report["procedures"]
    assert "ProcB" in report["procedures"]


def test_statement_keywords_not_treated_as_procedures(tmp_path: Path):
    report = make_cal(tmp_path, proc("MyProc", "IF SomeVar.FINDFIRST THEN", "  SomeVar.MODIFY;")).parse()
    assert "IF" not in report["procedures"]
    assert "MyProc" in report["procedures"]


def test_event_procedure_flagged(tmp_path: Path):
    report = make_cal(tmp_path, proc("OnAfterInsert", "x := 1;")).parse()
    assert report["procedures"]["OnAfterInsert"]["is_event"] is True


def test_non_event_procedure_not_flagged(tmp_path: Path):
    report = make_cal(tmp_path, proc("DoWork", "x := 1;")).parse()
    assert report["procedures"]["DoWork"]["is_event"] is False


# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------


def test_base_complexity_is_one(tmp_path: Path):
    report = make_cal(tmp_path, proc("Simple", "x := 1;")).parse()
    assert report["procedures"]["Simple"]["complexity"] == 1


def test_if_increments_complexity(tmp_path: Path):
    report = make_cal(tmp_path, proc("HasIf", "IF x = 1 THEN y := 2;")).parse()
    assert report["procedures"]["HasIf"]["complexity"] >= 2


def test_while_increments_complexity(tmp_path: Path):
    report = make_cal(tmp_path, proc("HasWhile", "WHILE x > 0 DO x := x - 1;")).parse()
    assert report["procedures"]["HasWhile"]["complexity"] >= 2


def test_total_complexity_sums_all_procedures(tmp_path: Path):
    cal = proc("A", "IF x = 1 THEN", "  y := 1;") + "\n" + proc("B", "IF z = 2 THEN", "  w := 2;")
    report = make_cal(tmp_path, cal).parse()
    assert report["complexity_score"] >= 4


# ---------------------------------------------------------------------------
# Read / write detection
# ---------------------------------------------------------------------------


def test_findset_detected_as_read(tmp_path: Path):
    report = make_cal(tmp_path, proc("DoRead", "SomeTable.FINDSET;")).parse()
    assert any(r["operation"] == "FINDSET" for r in report["procedures"]["DoRead"]["reads"])


def test_modify_detected_as_write(tmp_path: Path):
    report = make_cal(tmp_path, proc("DoWrite", "SomeTable.MODIFY;")).parse()
    assert any(w["operation"] == "MODIFY" for w in report["procedures"]["DoWrite"]["writes"])


def test_insert_detected_as_write(tmp_path: Path):
    report = make_cal(tmp_path, proc("DoInsert", "SomeTable.INSERT(TRUE);")).parse()
    assert any(w["operation"] == "INSERT" for w in report["procedures"]["DoInsert"]["writes"])


def test_delete_detected_as_write(tmp_path: Path):
    report = make_cal(tmp_path, proc("DoDel", "SomeTable.DELETE;")).parse()
    assert any(w["operation"] == "DELETE" for w in report["procedures"]["DoDel"]["writes"])


def test_commit_detected_as_write(tmp_path: Path):
    report = make_cal(tmp_path, proc("DoCommit", "COMMIT;")).parse()
    assert any(w["operation"] == "COMMIT" for w in report["procedures"]["DoCommit"]["writes"])


def test_side_effects_aggregated(tmp_path: Path):
    report = make_cal(tmp_path, proc("DoStuff", "SomeTable.INSERT;", "SomeTable.MODIFY;")).parse()
    ops = {se["operation"] for se in report["side_effects"]}
    assert "INSERT" in ops
    assert "MODIFY" in ops


# ---------------------------------------------------------------------------
# Dependency extraction
# ---------------------------------------------------------------------------


def test_codeunit_dependency_extracted(tmp_path: Path):
    report = make_cal(tmp_path, proc("MyProc", 'CODEUNIT::"Sales-Post";')).parse()
    assert "Sales-Post" in report["dependencies"]["codeunits"]


def test_report_dependency_extracted(tmp_path: Path):
    report = make_cal(tmp_path, proc("MyProc", 'REPORT::"Sales Invoice";')).parse()
    assert "Sales Invoice" in report["dependencies"]["reports"]


def test_page_dependency_extracted(tmp_path: Path):
    report = make_cal(tmp_path, proc("MyProc", 'PAGE::"Customer List";')).parse()
    assert "Customer List" in report["dependencies"]["pages"]


# ---------------------------------------------------------------------------
# Loop tracking
# ---------------------------------------------------------------------------


def test_read_inside_repeat_loop_flagged_in_loop(tmp_path: Path):
    report = make_cal(tmp_path, proc(
        "LoopProc",
        "REPEAT",
        "  SomeTable.FINDSET;",
        "UNTIL SomeTable.NEXT = 0;",
    )).parse()
    assert any(r.get("inLoop") for r in report["procedures"]["LoopProc"]["reads"])


def test_read_outside_loop_not_flagged_in_loop(tmp_path: Path):
    report = make_cal(tmp_path, proc("NoLoopProc", "SomeTable.FINDSET;")).parse()
    assert all(not r.get("inLoop") for r in report["procedures"]["NoLoopProc"]["reads"])


# ---------------------------------------------------------------------------
# Filter tracking
# ---------------------------------------------------------------------------


def test_findset_after_setrange_is_filtered(tmp_path: Path):
    report = make_cal(tmp_path, proc("FilteredRead", "SomeTable.SETRANGE(Field, Value);", "SomeTable.FINDSET;")).parse()
    reads = report["procedures"]["FilteredRead"]["reads"]
    findset = next((r for r in reads if r["operation"] == "FINDSET"), None)
    assert findset is not None
    assert findset["hasFilter"] is True


def test_findset_without_filter_is_unfiltered(tmp_path: Path):
    report = make_cal(tmp_path, proc("UnfilteredRead", "SomeTable.FINDSET;")).parse()
    reads = report["procedures"]["UnfilteredRead"]["reads"]
    findset = next((r for r in reads if r["operation"] == "FINDSET"), None)
    assert findset is not None
    assert findset["hasFilter"] is False


# ---------------------------------------------------------------------------
# CS companion metadata
# ---------------------------------------------------------------------------


def test_object_id_extracted_from_cs(tmp_path: Path):
    report = make_cal(
        tmp_path,
        proc("MyProc", "x := 1;"),
        cs_text='[NavCodeunit(42, "My Codeunit")]\nclass Codeunit42 : NavCodeunit {}',
    ).parse()
    assert report["object_id"] == 42


def test_object_name_extracted_from_cs(tmp_path: Path):
    report = make_cal(
        tmp_path,
        proc("MyProc", "x := 1;"),
        cs_text='[NavCodeunit(7, "Company-Initialize")]\nclass Codeunit7 : NavCodeunit {}',
    ).parse()
    assert report["object_name"] == "Company-Initialize"


def test_missing_cs_produces_warning(tmp_path: Path):
    report = make_cal(tmp_path, proc("MyProc", "x := 1;")).parse()
    assert any("companion" in w.lower() or ".cs" in w for w in report["warnings"])


# ---------------------------------------------------------------------------
# Temporary table detection
# ---------------------------------------------------------------------------


def test_temp_prefix_variable_is_detected_as_temp(tmp_path: Path):
    report = make_cal(tmp_path, proc("MyProc", "TempEntry.FINDSET;")).parse()
    reads = report["procedures"]["MyProc"]["reads"]
    # Parser uppercases the tableVar
    tmp_read = next((r for r in reads if "TEMP" in r["tableVar"].upper()), None)
    assert tmp_read is not None
    assert tmp_read["isTemporary"] is True
