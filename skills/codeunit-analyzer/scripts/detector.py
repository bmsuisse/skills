"""
Bottleneck detector (standalone, matching service implementation).
"""

from pathlib import Path
from typing import Any, Dict, List


class BottleneckDetector:
    """Detect bottlenecks matching service RuleEngine implementation."""

    def __init__(self, parsed_data, file_path, table_metadata=None):
        self.data = parsed_data
        self.file_path = Path(file_path)
        self.table_metadata = table_metadata or {}
        self.bottlenecks = []

    def detect(self):
        """Detect all bottlenecks using service RuleEngine logic."""
        raw_procedures = self.data.get("procedures", {})

        for proc_name, proc_data in raw_procedures.items():
            self._detect_procedure_bottlenecks(proc_name, proc_data)

        return self.bottlenecks

    def _get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table metadata info if available."""
        if not table_name or not self.table_metadata:
            return {}

        normalized_name = table_name.lower().strip()
        return self.table_metadata.get(normalized_name, {})

    def _get_table_impact_multiplier(self, table_name: str) -> float:
        """Get the impact multiplier for a table based on its size."""
        info = self._get_table_info(table_name)
        return info.get("impactMultiplier", 1.0)

    def _get_table_row_count(self, table_name: str) -> int:
        """Get the row count for a table."""
        info = self._get_table_info(table_name)
        return info.get("rowCount", 0)

    def _get_table_friendly_size(self, table_name: str) -> str:
        """Get a friendly size description for a table."""
        info = self._get_table_info(table_name)
        return info.get("friendlySize", "unknown size")

    def _get_table_severity_adjustment(self, table_name: str) -> str:
        """Get the severity adjustment description for a table."""
        info = self._get_table_info(table_name)
        return info.get("severityAdjustment", "unknown impact")

    def _detect_procedure_bottlenecks(self, proc_name: str, proc_data: dict):
        """Detect all bottleneck patterns in a procedure."""
        writes = [w["operation"] for w in proc_data.get("writes", []) if w["operation"] in ["INSERT", "MODIFY", "DELETE"]]
        has_commit = any(w["operation"] == "COMMIT" for w in proc_data.get("writes", []))

        # Pattern 1: Large transaction with COMMIT
        self._detect_large_transaction(proc_name, proc_data, has_commit)

        # Pattern 2: N+1 Query
        self._detect_n_plus_one_query(proc_name, proc_data)

        # Pattern 3: CALCFIELDS in loops
        self._detect_calcfields_in_loop(proc_name, proc_data)

        # Pattern 4: Heavy MODIFY operations
        self._detect_heavy_modify_operations(proc_name, proc_data, writes)

        # Pattern 5: Unfiltered FINDSET/FIND operations
        self._detect_unfiltered_reads(proc_name, proc_data)

        # Pattern 6: Nested loops with database operations
        self._detect_nested_loops_with_db_ops(proc_name, proc_data)

        # Pattern 7: Read-heavy procedures
        self._detect_read_heavy_procedure(proc_name, proc_data)

        # Pattern 8: Compound anti-patterns
        self._detect_compound_antipatterns(proc_name, proc_data, has_commit)

        # Pattern 9: Bulk DELETE operations
        self._detect_bulk_delete_operations(proc_name, proc_data, writes)

    def _detect_large_transaction(self, proc_name: str, proc_data: dict, has_commit: bool):
        """Pattern 1: Transaction size analysis."""
        if not has_commit:
            return

        real_writes = [w for w in proc_data.get("writes", []) if not w.get("isTemporary")]
        insert_count = sum(1 for w in real_writes if w["operation"] == "INSERT")
        modify_count = sum(1 for w in real_writes if w["operation"] == "MODIFY")
        delete_count = sum(1 for w in real_writes if w["operation"] == "DELETE")

        # Weight: DELETE=3, INSERT=2, MODIFY=1
        transaction_weight = delete_count * 3 + insert_count * 2 + modify_count

        if transaction_weight >= 30:
            severity = "critical" if transaction_weight >= 60 else "high"
            score = 60 + min(transaction_weight, 40)

            self.bottlenecks.append({
                "pattern": "large_transaction",
                "severity": severity,
                "score": score,
                "procedure": proc_name,
                "explanation": f"Large transaction with COMMIT (weight: {transaction_weight}). Contains {insert_count} INSERTs, {modify_count} MODIFYs, {delete_count} DELETEs. Explicit COMMIT prevents proper rollback on errors.",
                "recommendation": "Split into smaller transactions or remove COMMIT to allow NAV to handle transaction boundaries automatically.",
                "example": "// Avoid explicit COMMIT\n// Break into smaller logical units\n// Let NAV manage transactions",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id")
                }
            })

    def _detect_n_plus_one_query(self, proc_name: str, proc_data: dict):
        """Pattern 2: N+1 Query detection."""
        reads_in_loops = [r for r in proc_data.get("reads", []) if r.get("inLoop") and not r.get("isTemporary")]
        findset_in_loops = [r for r in reads_in_loops if r["operation"] == "FINDSET"]
        get_in_loops = [r for r in reads_in_loops if r["operation"] == "GET"]

        if len(findset_in_loops) < 2 and len(get_in_loops) < 5:
            return

        # Calculate impact multiplier based on table sizes
        tables_in_loops = list(set([r.get("tableName", "") for r in (findset_in_loops + get_in_loops) if r.get("tableName")]))
        max_impact_multiplier = 1.0
        table_size_info = []

        for table_name in tables_in_loops:
            if table_name and table_name != "Unknown":
                multiplier = self._get_table_impact_multiplier(table_name)
                friendly_size = self._get_table_friendly_size(table_name)
                max_impact_multiplier = max(max_impact_multiplier, multiplier)
                table_size_info.append(f"{table_name} ({friendly_size})")

        # Adjust severity based on table size
        base_severity = "critical" if (len(findset_in_loops) >= 3 or len(get_in_loops) >= 10) else "high"
        adjusted_score = int((85 + min(len(findset_in_loops) * 5, 15)) * max_impact_multiplier)

        if max_impact_multiplier >= 1.5 and base_severity == "high":
            severity = "critical"
        else:
            severity = base_severity

        affected_lines = [r["line"] for r in (findset_in_loops + get_in_loops)[:5]]
        tables_str = ", ".join(table_size_info) if table_size_info else "Unknown tables"

        self.bottlenecks.append({
            "pattern": "n_plus_one_query",
            "severity": severity,
            "score": adjusted_score,
            "procedure": proc_name,
            "explanation": f"N+1 query pattern detected: {len(findset_in_loops)} FINDSET and {len(get_in_loops)} GET operations inside loops. Affected tables: {tables_str}. Impact multiplier: {max_impact_multiplier}x",
            "recommendation": "Load all records at once using FINDSET with filters outside the loop, then process in memory. Use SETRANGE/SETFILTER before FINDSET to limit data.",
            "example": "// Good:\nTable.SETRANGE(Field, Value);\nIF Table.FINDSET THEN REPEAT\n  // Process\nUNTIL Table.NEXT = 0;",
            "codeunit": {
                "file": self.file_path.name,
                "object_name": self.data.get("object_name"),
                "object_id": self.data.get("object_id")
            }
        })

    def _detect_calcfields_in_loop(self, proc_name: str, proc_data: dict):
        """Pattern 3: CALCFIELDS in loops."""
        reads_in_loops = [r for r in proc_data.get("reads", []) if r.get("inLoop") and not r.get("isTemporary")]
        calcfields_in_loops = [r for r in reads_in_loops if r["operation"] == "CALCFIELDS"]
        calcsums_in_loops = [r for r in reads_in_loops if r["operation"] == "CALCSUMS"]

        if not calcfields_in_loops and not calcsums_in_loops:
            return

        total_calc_ops = len(calcfields_in_loops) + len(calcsums_in_loops)

        # Get table sizes for CALCFIELDS operations
        calc_tables = list(set([r.get("tableName", "") for r in (calcfields_in_loops + calcsums_in_loops) if r.get("tableName")]))
        max_impact_multiplier = 1.0
        table_size_info = []

        for table_name in calc_tables:
            if table_name and table_name != "Unknown":
                multiplier = self._get_table_impact_multiplier(table_name)
                friendly_size = self._get_table_friendly_size(table_name)
                max_impact_multiplier = max(max_impact_multiplier, multiplier)
                table_size_info.append(f"{table_name} ({friendly_size})")

        base_severity = "critical" if total_calc_ops >= 5 else "high"
        adjusted_score = int((80 + min(total_calc_ops * 5, 20)) * max_impact_multiplier)

        if max_impact_multiplier >= 1.5:
            severity = "critical"
        else:
            severity = base_severity

        affected_lines = [r["line"] for r in (calcfields_in_loops + calcsums_in_loops)[:5]]
        tables_str = ", ".join(table_size_info) if table_size_info else "Unknown tables"

        self.bottlenecks.append({
            "pattern": "calcfields_in_loop",
            "severity": severity,
            "score": adjusted_score,
            "procedure": proc_name,
            "explanation": f"CALCFIELDS/CALCSUMS called {total_calc_ops} times inside loops. Affected tables: {tables_str}. Each call triggers expensive aggregate calculations. Impact multiplier: {max_impact_multiplier}x",
            "recommendation": "Calculate flowfield values outside loops when possible, or use temporary tables to cache calculated values.",
            "example": "// Calculate once outside loop\nTable.CALCFIELDS(FlowField);\nCachedValue := Table.FlowField;\n// Use CachedValue in loop",
            "codeunit": {
                "file": self.file_path.name,
                "object_name": self.data.get("object_name"),
                "object_id": self.data.get("object_id")
            }
        })

    def _detect_heavy_modify_operations(self, proc_name: str, proc_data: dict, writes: List[str]):
        """Pattern 4: Heavy write operations."""
        modify_count = sum(1 for w in writes if w == "MODIFY")

        if modify_count >= 5:
            self.bottlenecks.append({
                "pattern": "heavy_modify_operations",
                "severity": "medium",
                "score": 50 + min(modify_count * 5, 30),
                "procedure": proc_name,
                "explanation": f"Procedure contains {modify_count} MODIFY operations. Each MODIFY triggers validation and updates, which can be slow.",
                "recommendation": "Consider using MODIFYALL for bulk updates when changing the same field across multiple records.",
                "example": "// Instead of loop with MODIFY:\nTable.SETRANGE(Status, 'Pending');\nTable.MODIFYALL(Status, 'Processed');",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id")
                }
            })

    def _detect_unfiltered_reads(self, proc_name: str, proc_data: dict):
        """Pattern 5: Unfiltered FINDSET/FIND operations."""
        unfiltered_reads = [
            r for r in proc_data.get("reads", [])
            if r["operation"] in ["FINDSET", "FIND"] and not r.get("hasFilter")
        ]

        if len(unfiltered_reads) < 2:
            return

        # Calculate impact based on actual table sizes
        tables_unfiltered = list(set([r.get("tableName", "") for r in unfiltered_reads if r.get("tableName")]))
        max_impact_multiplier = 1.0
        max_row_count = 0
        table_size_details = []

        for table_name in tables_unfiltered:
            if table_name and table_name != "Unknown":
                multiplier = self._get_table_impact_multiplier(table_name)
                row_count = self._get_table_row_count(table_name)
                friendly_size = self._get_table_friendly_size(table_name)
                severity_adj = self._get_table_severity_adjustment(table_name)

                max_impact_multiplier = max(max_impact_multiplier, multiplier)
                max_row_count = max(max_row_count, row_count)
                table_size_details.append(f"{table_name} ({friendly_size}, {severity_adj})")

        adjusted_score = int((70 + min(len(unfiltered_reads) * 5, 30)) * max_impact_multiplier)

        if max_impact_multiplier >= 2.0:
            severity = "critical"
        elif max_impact_multiplier >= 1.5:
            severity = "high"
        else:
            severity = "high"

        affected_lines = [r["line"] for r in unfiltered_reads[:5]]
        tables_str = ", ".join(table_size_details) if table_size_details else "Unknown tables"

        self.bottlenecks.append({
            "pattern": "unfiltered_table_reads",
            "severity": severity,
            "score": adjusted_score,
            "procedure": proc_name,
            "explanation": f"Found {len(unfiltered_reads)} unfiltered FINDSET/FIND operations. Affected tables: {tables_str}. Reading entire tables without filters causes full table scans. Impact multiplier: {max_impact_multiplier}x",
            "recommendation": "Always use SETRANGE or SETFILTER before FINDSET/FIND to limit the dataset. Add appropriate indexes if needed.",
            "example": "// Add filters:\nTable.SETRANGE(Date, StartDate, EndDate);\nTable.SETRANGE(Status, 'Active');\nIF Table.FINDSET THEN...",
            "codeunit": {
                "file": self.file_path.name,
                "object_name": self.data.get("object_name"),
                "object_id": self.data.get("object_id")
            }
        })

    def _detect_nested_loops_with_db_ops(self, proc_name: str, proc_data: dict):
        """Pattern 6: Nested loops with database operations."""
        max_loop_depth = proc_data.get("max_loop_depth", 0)
        reads_in_loops = [r for r in proc_data.get("reads", []) if r.get("inLoop") and not r.get("isTemporary")]

        if max_loop_depth >= 2 and reads_in_loops:
            self.bottlenecks.append({
                "pattern": "nested_loops_with_database_ops",
                "severity": "critical",
                "score": 90,
                "procedure": proc_name,
                "explanation": f"Nested loops (depth: {max_loop_depth}) with {len(reads_in_loops)} database operations. Causes exponential performance degradation (O(n²) or worse).",
                "recommendation": "Restructure to use single loop with optimized queries. Consider using temporary tables or in-memory processing.",
                "example": "// Avoid nested loops with DB ops\n// Load data into temp table first\n// Process in single loop",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id")
                }
            })

    def _detect_read_heavy_procedure(self, proc_name: str, proc_data: dict):
        """Pattern 7: Read-heavy procedures."""
        real_reads = [
            r for r in proc_data.get("reads", [])
            if not r.get("isTemporary") and r["operation"] not in ["SETRANGE", "SETFILTER"]
        ]

        if len(real_reads) >= 15:
            self.bottlenecks.append({
                "pattern": "read_heavy_procedure",
                "severity": "medium",
                "score": 50 + min(len(real_reads), 30),
                "procedure": proc_name,
                "explanation": f"Procedure performs {len(real_reads)} database read operations. High read count indicates potential for optimization.",
                "recommendation": "Review if all reads are necessary. Consider caching frequently accessed data in temporary tables or using joins/filters more efficiently.",
                "example": "// Cache data in temp table\n// Reduce redundant lookups\n// Use SETLOADFIELDS to reduce data transfer",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id")
                }
            })

    def _detect_compound_antipatterns(self, proc_name: str, proc_data: dict, has_commit: bool):
        """Pattern 8: Compound anti-patterns (multiple issues amplify each other)."""
        reads_in_loops = [r for r in proc_data.get("reads", []) if r.get("inLoop") and not r.get("isTemporary")]
        findset_in_loops = [r for r in reads_in_loops if r["operation"] == "FINDSET"]
        get_in_loops = [r for r in reads_in_loops if r["operation"] == "GET"]

        issues = []
        if proc_data.get("max_loop_depth", 0) >= 2:
            issues.append("nested_loops")
        if any(r["operation"] == "CALCFIELDS" and r.get("inLoop") for r in proc_data.get("reads", [])):
            issues.append("calcfields_in_loop")
        if has_commit:
            issues.append("explicit_commit")
        if len(findset_in_loops) >= 2 or len(get_in_loops) >= 5:
            issues.append("n_plus_one_query")
        if len([r for r in proc_data.get("reads", []) if r["operation"] in ["FINDSET", "FIND"] and not r.get("hasFilter")]) >= 2:
            issues.append("unfiltered_reads")

        if len(issues) >= 3:
            issues_str = ", ".join(issues)
            self.bottlenecks.append({
                "pattern": "compound_antipattern",
                "severity": "critical",
                "score": 95,
                "procedure": proc_name,
                "explanation": f"Multiple anti-patterns detected: {issues_str}. These issues compound each other, causing severe performance degradation.",
                "recommendation": "Address all identified anti-patterns. Start with the highest severity issues first. Consider complete refactoring of this procedure.",
                "example": "// Requires comprehensive refactoring\n// Prioritize:\n// 1. Remove nested loops\n// 2. Fix N+1 queries\n// 3. Add filters\n// 4. Remove COMMIT",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id")
                }
            })

    def _detect_bulk_delete_operations(self, proc_name: str, proc_data: dict, writes: List[str]):
        """Pattern 9: Many DELETE operations."""
        delete_count = sum(1 for w in writes if w == "DELETE")

        if delete_count >= 4:
            severity = "high" if delete_count >= 10 else "medium"
            self.bottlenecks.append({
                "pattern": "bulk_delete_operations",
                "severity": severity,
                "score": 65 + min(delete_count * 7, 35),
                "procedure": proc_name,
                "explanation": f"Procedure contains {delete_count} DELETE operations. Individual DELETEs in loops are slow and trigger cascading deletes.",
                "recommendation": "Use DELETEALL for bulk deletions when possible. Ensure proper SETRANGE/SETFILTER before DELETEALL.",
                "example": "// Instead of loop with DELETE:\nTable.SETRANGE(Status, 'Obsolete');\nTable.DELETEALL(TRUE);  // TRUE = run triggers",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id")
                }
            })
