"""Tests for BottleneckDetector (detector.py)."""

from scripts.detector import BottleneckDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_proc(**kwargs) -> dict:
    defaults: dict = {
        "params": "",
        "returnType": None,
        "calls": [],
        "calls_in_loop": [],
        "writes": [],
        "reads": [],
        "guards": [],
        "is_event": False,
        "complexity": 1,
        "lines": [],
        "nesting_depth": 0,
        "max_loop_depth": 0,
        "variables": {},
    }
    defaults.update(kwargs)
    return defaults


def make_parsed(procedures: dict, object_name: str = "TestCodeunit", object_id: int = 1) -> dict:
    return {
        "object_id": object_id,
        "object_name": object_name,
        "complexity_score": 1,
        "procedures": procedures,
        "side_effects": [],
        "dependencies": {"tables": [], "codeunits": [], "reports": [], "pages": [], "xmlports": []},
        "warnings": [],
        "source_code": "",
        "tableVariables": {},
        "temporaryTables": [],
    }


def detect(procedures: dict, file_path: str = "test.c-al") -> list:
    bottlenecks = BottleneckDetector(make_parsed(procedures), file_path).detect()
    return bottlenecks


def patterns(bottlenecks: list) -> list[str]:
    return [b["pattern"] for b in bottlenecks]


# ---------------------------------------------------------------------------
# Pattern 1: Large transaction with COMMIT
# ---------------------------------------------------------------------------


def test_no_commit_no_large_transaction():
    writes = [{"operation": "INSERT", "isTemporary": False} for _ in range(20)]
    assert "large_transaction" not in patterns(detect({"P": make_proc(writes=writes)}))


def test_small_transaction_with_commit_no_bottleneck():
    # 5 DELETEs × 3 = 15, below threshold 30
    writes = [{"operation": "COMMIT"}] + [{"operation": "DELETE", "isTemporary": False} for _ in range(5)]
    assert "large_transaction" not in patterns(detect({"P": make_proc(writes=writes)}))


def test_large_transaction_detected():
    # 10 DELETEs × 3 = 30, hits threshold
    writes = [{"operation": "COMMIT"}] + [{"operation": "DELETE", "isTemporary": False} for _ in range(10)]
    assert "large_transaction" in patterns(detect({"P": make_proc(writes=writes)}))


def test_large_transaction_severity_critical_at_weight_60():
    # 20 DELETEs × 3 = 60 → critical
    writes = [{"operation": "COMMIT"}] + [{"operation": "DELETE", "isTemporary": False} for _ in range(20)]
    bt = next(b for b in detect({"P": make_proc(writes=writes)}) if b["pattern"] == "large_transaction")
    assert bt["severity"] == "critical"


# ---------------------------------------------------------------------------
# Pattern 2: N+1 query
# ---------------------------------------------------------------------------


def _findset_in_loop() -> dict:
    return {"operation": "FINDSET", "inLoop": True, "isTemporary": False, "tableName": "Entry", "line": "SomeTable.FINDSET"}


def _get_in_loop() -> dict:
    return {"operation": "GET", "inLoop": True, "isTemporary": False, "tableName": "Entry", "line": "SomeTable.GET(Key)"}


def test_single_findset_in_loop_no_n_plus_one():
    assert "n_plus_one_query" not in patterns(detect({"P": make_proc(reads=[_findset_in_loop()])}))


def test_two_findsets_in_loop_triggers_n_plus_one():
    reads = [_findset_in_loop(), _findset_in_loop()]
    assert "n_plus_one_query" in patterns(detect({"P": make_proc(reads=reads)}))


def test_five_gets_in_loop_triggers_n_plus_one():
    reads = [_get_in_loop() for _ in range(5)]
    assert "n_plus_one_query" in patterns(detect({"P": make_proc(reads=reads)}))


def test_temporary_reads_do_not_trigger_n_plus_one():
    reads = [{"operation": "FINDSET", "inLoop": True, "isTemporary": True, "tableName": "TempEntry", "line": "T.FINDSET"} for _ in range(3)]
    assert "n_plus_one_query" not in patterns(detect({"P": make_proc(reads=reads)}))


# ---------------------------------------------------------------------------
# Pattern 3: CALCFIELDS in loops
# ---------------------------------------------------------------------------


def test_calcfields_in_loop_detected():
    reads = [{"operation": "CALCFIELDS", "inLoop": True, "isTemporary": False, "tableName": "Entry", "line": "T.CALCFIELDS(F)"}]
    assert "calcfields_in_loop" in patterns(detect({"P": make_proc(reads=reads)}))


def test_calcfields_outside_loop_not_detected():
    reads = [{"operation": "CALCFIELDS", "inLoop": False, "isTemporary": False, "tableName": "Entry", "line": "T.CALCFIELDS(F)"}]
    assert "calcfields_in_loop" not in patterns(detect({"P": make_proc(reads=reads)}))


# ---------------------------------------------------------------------------
# Pattern 4: Heavy MODIFY operations
# ---------------------------------------------------------------------------


def test_four_modifies_no_bottleneck():
    writes = [{"operation": "MODIFY", "isTemporary": False} for _ in range(4)]
    assert "heavy_modify_operations" not in patterns(detect({"P": make_proc(writes=writes)}))


def test_five_modifies_triggers():
    writes = [{"operation": "MODIFY", "isTemporary": False} for _ in range(5)]
    assert "heavy_modify_operations" in patterns(detect({"P": make_proc(writes=writes)}))


# ---------------------------------------------------------------------------
# Pattern 5: Unfiltered reads
# ---------------------------------------------------------------------------


def test_single_unfiltered_findset_no_bottleneck():
    reads = [{"operation": "FINDSET", "hasFilter": False, "tableName": "Entry", "line": "T.FINDSET"}]
    assert "unfiltered_table_reads" not in patterns(detect({"P": make_proc(reads=reads)}))


def test_two_unfiltered_findsets_triggers():
    reads = [{"operation": "FINDSET", "hasFilter": False, "tableName": "Entry", "line": "T.FINDSET"} for _ in range(2)]
    assert "unfiltered_table_reads" in patterns(detect({"P": make_proc(reads=reads)}))


def test_filtered_findsets_do_not_trigger():
    reads = [{"operation": "FINDSET", "hasFilter": True, "tableName": "Entry", "line": "T.FINDSET"} for _ in range(2)]
    assert "unfiltered_table_reads" not in patterns(detect({"P": make_proc(reads=reads)}))


# ---------------------------------------------------------------------------
# Pattern 6: Nested loops with DB ops
# ---------------------------------------------------------------------------


def test_loop_depth_1_not_triggered():
    reads = [{"operation": "FINDSET", "inLoop": True, "isTemporary": False, "tableName": "X", "line": "X.FINDSET"}]
    assert "nested_loops_with_database_ops" not in patterns(detect({"P": make_proc(reads=reads, max_loop_depth=1)}))


def test_loop_depth_2_with_reads_triggers():
    reads = [{"operation": "FINDSET", "inLoop": True, "isTemporary": False, "tableName": "X", "line": "X.FINDSET"}]
    assert "nested_loops_with_database_ops" in patterns(detect({"P": make_proc(reads=reads, max_loop_depth=2)}))


def test_loop_depth_2_without_reads_not_triggered():
    assert "nested_loops_with_database_ops" not in patterns(detect({"P": make_proc(reads=[], max_loop_depth=2)}))


# ---------------------------------------------------------------------------
# Pattern 7: Read-heavy procedures
# ---------------------------------------------------------------------------


def test_14_real_reads_no_bottleneck():
    reads = [{"operation": "FINDFIRST", "isTemporary": False} for _ in range(14)]
    assert "read_heavy_procedure" not in patterns(detect({"P": make_proc(reads=reads)}))


def test_15_real_reads_triggers():
    reads = [{"operation": "FINDFIRST", "isTemporary": False} for _ in range(15)]
    assert "read_heavy_procedure" in patterns(detect({"P": make_proc(reads=reads)}))


def test_setrange_excluded_from_read_heavy_count():
    reads = [{"operation": "SETRANGE", "isTemporary": False} for _ in range(15)]
    assert "read_heavy_procedure" not in patterns(detect({"P": make_proc(reads=reads)}))


# ---------------------------------------------------------------------------
# Pattern 9: Bulk DELETE operations
# ---------------------------------------------------------------------------


def test_three_deletes_no_bulk_bottleneck():
    writes = [{"operation": "DELETE", "isTemporary": False} for _ in range(3)]
    assert "bulk_delete_operations" not in patterns(detect({"P": make_proc(writes=writes)}))


def test_four_deletes_triggers_bulk():
    writes = [{"operation": "DELETE", "isTemporary": False} for _ in range(4)]
    assert "bulk_delete_operations" in patterns(detect({"P": make_proc(writes=writes)}))


def test_ten_deletes_severity_high():
    writes = [{"operation": "DELETE", "isTemporary": False} for _ in range(10)]
    bt = next(b for b in detect({"P": make_proc(writes=writes)}) if b["pattern"] == "bulk_delete_operations")
    assert bt["severity"] == "high"


# ---------------------------------------------------------------------------
# Codeunit metadata propagated into bottleneck reports
# ---------------------------------------------------------------------------


def test_codeunit_metadata_present_in_bottleneck():
    writes = [{"operation": "COMMIT"}] + [{"operation": "DELETE", "isTemporary": False} for _ in range(10)]
    data = make_parsed({"P": make_proc(writes=writes)}, object_name="My CU", object_id=99)
    bottlenecks = BottleneckDetector(data, "mycodeunit.c-al").detect()
    bt = next(b for b in bottlenecks if b["pattern"] == "large_transaction")
    assert bt["codeunit"]["object_name"] == "My CU"
    assert bt["codeunit"]["object_id"] == 99
    assert bt["codeunit"]["file"] == "mycodeunit.c-al"
