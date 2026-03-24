from pathlib import Path
from typing import Any, Dict, List


class BottleneckDetector:
    def __init__(self, parsed_data, file_path, table_metadata=None):
        self.data = parsed_data
        self.file_path = Path(file_path)
        self.table_metadata = table_metadata or {}
        self.bottlenecks = []

    def detect(self):
        raw_procedures = self.data.get("procedures", {})

        for proc_name, proc_data in raw_procedures.items():
            self._detect_procedure_bottlenecks(proc_name, proc_data)

        self._detect_index_recommendations()

        return self.bottlenecks

    def _get_table_info(self, table_name: str) -> Dict[str, Any]:
        if not table_name or not self.table_metadata:
            return {}

        normalized_name = table_name.lower().strip()
        return self.table_metadata.get(normalized_name, {})

    def _get_table_impact_multiplier(self, table_name: str) -> float:
        return self._get_table_info(table_name).get("impactMultiplier", 1.0)

    def _get_table_row_count(self, table_name: str) -> int:
        return self._get_table_info(table_name).get("rowCount", 0)

    def _get_table_friendly_size(self, table_name: str) -> str:
        return self._get_table_info(table_name).get("friendlySize", "unknown size")

    def _get_table_severity_adjustment(self, table_name: str) -> str:
        return self._get_table_info(table_name).get("severityAdjustment", "unknown impact")

    def _detect_procedure_bottlenecks(self, proc_name: str, proc_data: dict):
        writes = [
            w["operation"] for w in proc_data.get("writes", []) if w["operation"] in ["INSERT", "MODIFY", "DELETE"]
        ]
        has_commit = any(w["operation"] == "COMMIT" for w in proc_data.get("writes", []))

        self._detect_large_transaction(proc_name, proc_data, has_commit)
        self._detect_n_plus_one_query(proc_name, proc_data)
        self._detect_calcfields_in_loop(proc_name, proc_data)
        self._detect_heavy_modify_operations(proc_name, proc_data, writes)
        self._detect_unfiltered_reads(proc_name, proc_data)
        self._detect_nested_loops_with_db_ops(proc_name, proc_data)
        self._detect_read_heavy_procedure(proc_name, proc_data)
        self._detect_compound_antipatterns(proc_name, proc_data, has_commit)
        self._detect_bulk_delete_operations(proc_name, proc_data, writes)
        self._detect_validate_in_loop(proc_name, proc_data)
        self._detect_modify_in_onmodify(proc_name, proc_data)
        self._detect_multi_get_onvalidate(proc_name, proc_data)
        self._detect_commit_in_page_trigger(proc_name, proc_data, has_commit)
        self._detect_heavy_get_in_hot_trigger(proc_name, proc_data)
        self._detect_calcfields_in_hot_trigger(proc_name, proc_data)
        self._detect_modify_in_hot_trigger(proc_name, proc_data)
        self._detect_page_run_in_hot_trigger(proc_name, proc_data)
        self._detect_heavy_onclosepage(proc_name, proc_data)
        self._detect_missing_setloadfields(proc_name, proc_data)
        self._detect_unfiltered_findset(proc_name, proc_data)
        self._detect_event_subscriber_hotspot(proc_name, proc_data)

    def _detect_large_transaction(self, proc_name: str, proc_data: dict, has_commit: bool):
        if not has_commit:
            return

        real_writes = [w for w in proc_data.get("writes", []) if not w.get("isTemporary")]
        insert_count = sum(1 for w in real_writes if w["operation"] == "INSERT")
        modify_count = sum(1 for w in real_writes if w["operation"] == "MODIFY")
        delete_count = sum(1 for w in real_writes if w["operation"] == "DELETE")

        transaction_weight = delete_count * 3 + insert_count * 2 + modify_count

        if transaction_weight >= 30:
            severity = "critical" if transaction_weight >= 60 else "high"
            score = 60 + min(transaction_weight, 40)

            self.bottlenecks.append(
                {
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
                        "object_id": self.data.get("object_id"),
                    },
                }
            )

    def _detect_n_plus_one_query(self, proc_name: str, proc_data: dict):
        reads_in_loops = [r for r in proc_data.get("reads", []) if r.get("inLoop") and not r.get("isTemporary")]
        findset_in_loops = [r for r in reads_in_loops if r["operation"] == "FINDSET"]
        get_in_loops = [r for r in reads_in_loops if r["operation"] == "GET"]

        if len(findset_in_loops) < 2 and len(get_in_loops) < 5:
            return

        tables_in_loops = list(
            set([r.get("tableName", "") for r in (findset_in_loops + get_in_loops) if r.get("tableName")])
        )
        max_impact_multiplier = 1.0
        table_size_info = []

        for table_name in tables_in_loops:
            if table_name and table_name != "Unknown":
                multiplier = self._get_table_impact_multiplier(table_name)
                friendly_size = self._get_table_friendly_size(table_name)
                max_impact_multiplier = max(max_impact_multiplier, multiplier)
                table_size_info.append(f"{table_name} ({friendly_size})")

        base_severity = "critical" if (len(findset_in_loops) >= 3 or len(get_in_loops) >= 10) else "high"
        adjusted_score = int((85 + min(len(findset_in_loops) * 5, 15)) * max_impact_multiplier)

        if max_impact_multiplier >= 1.5 and base_severity == "high":
            severity = "critical"
        else:
            severity = base_severity

        affected_lines = [r["line"] for r in (findset_in_loops + get_in_loops)[:5]]
        tables_str = ", ".join(table_size_info) if table_size_info else "Unknown tables"

        self.bottlenecks.append(
            {
                "pattern": "n_plus_one_query",
                "severity": severity,
                "score": adjusted_score,
                "procedure": proc_name,
                "explanation": f"N+1 query pattern detected: {len(findset_in_loops)} FINDSET and {len(get_in_loops)} GET operations inside loops. Affected tables: {tables_str}. Impact multiplier: {max_impact_multiplier}x",
                "recommendation": "Load all records at once using FINDSET with filters outside the loop, then process in memory. Use SETRANGE/SETFILTER before FINDSET to limit data.",
                "example": "// Good:\nTable.SETRANGE(Field, Value);\nIF Table.FINDSET THEN REPEAT\n  // Process\nUNTIL Table.NEXT = 0;",
                "affected_lines": affected_lines,
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id"),
                },
            }
        )

    def _detect_calcfields_in_loop(self, proc_name: str, proc_data: dict):
        reads_in_loops = [r for r in proc_data.get("reads", []) if r.get("inLoop") and not r.get("isTemporary")]
        calcfields_in_loops = [r for r in reads_in_loops if r["operation"] == "CALCFIELDS"]
        calcsums_in_loops = [r for r in reads_in_loops if r["operation"] == "CALCSUMS"]

        if not calcfields_in_loops and not calcsums_in_loops:
            return

        total_calc_ops = len(calcfields_in_loops) + len(calcsums_in_loops)

        calc_tables = list(
            set([r.get("tableName", "") for r in (calcfields_in_loops + calcsums_in_loops) if r.get("tableName")])
        )
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

        self.bottlenecks.append(
            {
                "pattern": "calcfields_in_loop",
                "severity": severity,
                "score": adjusted_score,
                "procedure": proc_name,
                "explanation": f"CALCFIELDS/CALCSUMS called {total_calc_ops} times inside loops. Affected tables: {tables_str}. Each call triggers expensive aggregate calculations. Impact multiplier: {max_impact_multiplier}x",
                "recommendation": "Calculate flowfield values outside loops when possible, or use temporary tables to cache calculated values.",
                "example": "// Calculate once outside loop\nTable.CALCFIELDS(FlowField);\nCachedValue := Table.FlowField;\n// Use CachedValue in loop",
                "affected_lines": affected_lines,
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id"),
                },
            }
        )

    def _detect_heavy_modify_operations(self, proc_name: str, proc_data: dict, writes: List[str]):
        modify_count = sum(1 for w in writes if w == "MODIFY")

        if modify_count >= 5:
            self.bottlenecks.append(
                {
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
                        "object_id": self.data.get("object_id"),
                    },
                }
            )

    def _detect_unfiltered_reads(self, proc_name: str, proc_data: dict):
        unfiltered_reads = [
            r for r in proc_data.get("reads", []) if r["operation"] in ["FINDSET", "FIND"] and not r.get("hasFilter")
        ]

        if len(unfiltered_reads) < 2:
            return

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
        else:
            severity = "high"

        affected_lines = [r["line"] for r in unfiltered_reads[:5]]
        tables_str = ", ".join(table_size_details) if table_size_details else "Unknown tables"

        self.bottlenecks.append(
            {
                "pattern": "unfiltered_table_reads",
                "severity": severity,
                "score": adjusted_score,
                "procedure": proc_name,
                "explanation": f"Found {len(unfiltered_reads)} unfiltered FINDSET/FIND operations. Affected tables: {tables_str}. Reading entire tables without filters causes full table scans. Impact multiplier: {max_impact_multiplier}x",
                "recommendation": "Always use SETRANGE or SETFILTER before FINDSET/FIND to limit the dataset. Add appropriate indexes if needed.",
                "example": "// Add filters:\nTable.SETRANGE(Date, StartDate, EndDate);\nTable.SETRANGE(Status, 'Active');\nIF Table.FINDSET THEN...",
                "affected_lines": affected_lines,
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id"),
                },
            }
        )

    def _detect_nested_loops_with_db_ops(self, proc_name: str, proc_data: dict):
        max_loop_depth = proc_data.get("max_loop_depth", 0)
        reads_in_loops = [r for r in proc_data.get("reads", []) if r.get("inLoop") and not r.get("isTemporary")]

        if max_loop_depth >= 2 and reads_in_loops:
            self.bottlenecks.append(
                {
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
                        "object_id": self.data.get("object_id"),
                    },
                }
            )

    def _detect_read_heavy_procedure(self, proc_name: str, proc_data: dict):
        real_reads = [
            r
            for r in proc_data.get("reads", [])
            if not r.get("isTemporary") and r["operation"] not in ["SETRANGE", "SETFILTER"]
        ]

        if len(real_reads) >= 15:
            self.bottlenecks.append(
                {
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
                        "object_id": self.data.get("object_id"),
                    },
                }
            )

    def _detect_compound_antipatterns(self, proc_name: str, proc_data: dict, has_commit: bool):
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
        if (
            len(
                [
                    r
                    for r in proc_data.get("reads", [])
                    if r["operation"] in ["FINDSET", "FIND"] and not r.get("hasFilter")
                ]
            )
            >= 2
        ):
            issues.append("unfiltered_reads")

        if len(issues) >= 3:
            issues_str = ", ".join(issues)
            self.bottlenecks.append(
                {
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
                        "object_id": self.data.get("object_id"),
                    },
                }
            )

    def _detect_bulk_delete_operations(self, proc_name: str, proc_data: dict, writes: List[str]):
        delete_count = sum(1 for w in writes if w == "DELETE")

        if delete_count >= 4:
            severity = "high" if delete_count >= 10 else "medium"
            self.bottlenecks.append(
                {
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
                        "object_id": self.data.get("object_id"),
                    },
                }
            )

    def _detect_validate_in_loop(self, proc_name: str, proc_data: dict):
        validates = [
            w for w in proc_data.get("writes", []) if w["operation"] == "VALIDATE" and w.get("inLoop")
        ]
        if validates:
            self.bottlenecks.append({
                "pattern": "validate_in_loop",
                "severity": "high",
                "score": 130,
                "procedure": proc_name,
                "explanation": "VALIDATE called inside a loop. Firing field triggers repeatedly inside loops multiplies database load exponentially.",
                "recommendation": "Assign values directly if triggers are not required, or cache logic outside the loop.",
                "example": "// Assign without firing trigger:\nTable.Field := Value;\n// Then call Table.MODIFY(TRUE); after the loop",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id"),
                },
            })

    def _detect_modify_in_onmodify(self, proc_name: str, proc_data: dict):
        if "modify" not in proc_name.lower():
            return
        modifies = [
            w for w in proc_data.get("writes", []) if w["operation"] == "MODIFY"
        ]
        if modifies:
            self.bottlenecks.append({
                "pattern": "modify_in_onmodify",
                "severity": "critical",
                "score": 200,
                "procedure": proc_name,
                "explanation": "Calling MODIFY inside an OnModify trigger causes a recursive loop risk.",
                "recommendation": "Do not explicitly call MODIFY inside OnModify (or use a different table instance if necessary).",
                "example": "Remove the explicitly bare MODIFY call inside OnModify.",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id"),
                },
            })

    def _detect_multi_get_onvalidate(self, proc_name: str, proc_data: dict):
        if "validate" not in proc_name.lower():
            return
        gets = [
            r for r in proc_data.get("reads", []) if r["operation"] == "GET"
        ]
        if len(gets) >= 3:
            self.bottlenecks.append({
                "pattern": "multi_get_in_onvalidate",
                "severity": "medium",
                "score": 70,
                "procedure": proc_name,
                "explanation": f"Multiple GET calls ({len(gets)}) in a single OnValidate. Makes field entry feel sluggish.",
                "recommendation": "Cache frequently fetched records or simplify validation checks to minimize lookups.",
                "example": "Use Temp Tables, Cache Data Codeunits, or check if the record is already loaded.",
                "codeunit": {
                    "file": self.file_path.name,
                    "object_name": self.data.get("object_name"),
                    "object_id": self.data.get("object_id"),
                },
            })


    def _is_hot_trigger(self, proc_name: str) -> bool:
        lower_name = proc_name.lower()
        return any(ht in lower_name for ht in ["onaftergetrecord", "onaftergetcurrrecord", "onfindrecord", "onnextrecord"])

    def _detect_commit_in_page_trigger(self, proc_name: str, proc_data: dict, has_commit: bool):
        if not has_commit: return
        page_triggers = ["oninit", "onopenpage", "onclosepage", "onaftergetrecord", "onaftergetcurrrecord", "onnewrecord", "oninsertrecord", "onmodifyrecord", "ondeleterecord", "onqueryclosepage", "onfindrecord", "onnextrecord", "onaction", "ondrilldown", "onassistedit", "onlookup"]
        lower_name = proc_name.lower()
        if any(pt in lower_name for pt in page_triggers):
            self.bottlenecks.append({
                "pattern": "commit_in_page_trigger",
                "severity": "critical",
                "score": 180,
                "procedure": proc_name,
                "explanation": "COMMIT inside a page trigger breaks transaction rollback and can corrupt partial writes.",
                "recommendation": "Remove COMMIT from page triggers to ensure UI actions can be rolled back on error.",
                "example": "Remove the COMMIT statement.",
                "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
            })

    def _detect_heavy_get_in_hot_trigger(self, proc_name: str, proc_data: dict):
        if not self._is_hot_trigger(proc_name): return
        gets = [r for r in proc_data.get("reads", []) if r["operation"] == "GET"]
        if len(gets) >= 3:
            self.bottlenecks.append({
                "pattern": "heavy_get_in_hot_trigger",
                "severity": "critical",
                "score": 160,
                "procedure": proc_name,
                "explanation": f"Multiple GETs ({len(gets)}) in hot trigger. Fires on every record scroll, causing 1 DB round-trip per GET.",
                "recommendation": "Use FlowFields, cache records in memory, or use a temporary table.",
                "example": "Cache records outside the scrolling logic.",
                "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
            })

    def _detect_calcfields_in_hot_trigger(self, proc_name: str, proc_data: dict):
        if not self._is_hot_trigger(proc_name): return
        calcs = [r for r in proc_data.get("reads", []) if r["operation"] in ["CALCFIELDS", "CALCSUMS"] and not r.get("inLoop")]
        if len(calcs) >= 2:
            self.bottlenecks.append({
                "pattern": "calcfields_in_hot_trigger",
                "severity": "high",
                "score": 110,
                "procedure": proc_name,
                "explanation": f"Multiple CALCFIELDS ({len(calcs)}) in hot trigger (outside loops). Expensive per navigation.",
                "recommendation": "Calculate once before opening if possible, or only on drill-down.",
                "example": "Change UI to calculate on demand.",
                "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
            })

    def _detect_modify_in_hot_trigger(self, proc_name: str, proc_data: dict):
        if not self._is_hot_trigger(proc_name): return
        writes = [w for w in proc_data.get("writes", []) if w["operation"] in ["MODIFY", "INSERT", "DELETE"] and not w.get("isTemporary")]
        if writes:
            self.bottlenecks.append({
                "pattern": "db_write_in_hot_trigger",
                "severity": "high",
                "score": 120,
                "procedure": proc_name,
                "explanation": "Database write during a navigation/hot trigger causes unexpected saves and performance issues.",
                "recommendation": "Move writes to OnAction or explicit save functions.",
                "example": "Do not write during OnAfterGetRecord.",
                "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
            })

    def _detect_page_run_in_hot_trigger(self, proc_name: str, proc_data: dict):
        if not self._is_hot_trigger(proc_name): return
        calls = proc_data.get("calls", [])
        if any(c.upper() in ["PAGE.RUN", "PAGE.RUNMODAL"] for c in calls):
            self.bottlenecks.append({
                "pattern": "page_run_in_hot_trigger",
                "severity": "high",
                "score": 100,
                "procedure": proc_name,
                "explanation": "Opening a page from within a navigation trigger can cause recursive page loads.",
                "recommendation": "Trigger PAGE.RUN from an explicit user action (OnAction).",
                "example": "Move PAGE.RUN to an action.",
                "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
            })

    def _detect_heavy_onclosepage(self, proc_name: str, proc_data: dict):
        if "onclosepage" not in proc_name.lower(): return
        writes = [w for w in proc_data.get("writes", []) if w["operation"] in ["MODIFY", "INSERT", "DELETE", "DELETEALL", "MODIFYALL"] and not w.get("isTemporary")]
        if len(writes) >= 2:
            self.bottlenecks.append({
                "pattern": "heavy_onclosepage",
                "severity": "medium",
                "score": 70,
                "procedure": proc_name,
                "explanation": f"Multiple DB Writes ({len(writes)}) in OnClosePage. OnClosePage is not transactional; failures are swallowed.",
                "recommendation": "Perform heavy writes on an explicit 'Save' or 'Post' action, not silently on close.",
                "example": "Move writes out of OnClosePage.",
                "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
            })

    def _detect_missing_setloadfields(self, proc_name: str, proc_data: dict):
        reads = [r for r in proc_data.get("reads", []) if r["operation"] in ["FINDSET", "FINDFIRST", "FIND"] and not r.get("isTemporary")]
        for read in reads:
            if not read.get("hasLoadFields"):
                self.bottlenecks.append({
                    "pattern": "missing_setloadfields",
                    "severity": "medium",
                    "score": 60,
                    "procedure": proc_name,
                    "explanation": f"Missing SetLoadFields before {read['operation']} for table {read.get('tableName', 'Unknown')}. This causes NAV to fetch all fields (SELECT *) across the network.",
                    "recommendation": "Use SetLoadFields to specify exactly which fields you need before executing the read.",
                    "example": "Table.SETLOADFIELDS(Field1, Field2);\\nIF Table.FINDSET THEN...",
                    "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
                })

    def _detect_unfiltered_findset(self, proc_name: str, proc_data: dict):
        reads = [r for r in proc_data.get("reads", []) if r["operation"] == "FINDSET" and not r.get("isTemporary")]
        for read in reads:
            if not read.get("hasFilter"):
                self.bottlenecks.append({
                    "pattern": "unfiltered_findset",
                    "severity": "high",
                    "score": 110,
                    "procedure": proc_name,
                    "explanation": f"Unfiltered FINDSET detected for table {read.get('tableName', 'Unknown')}. This will pull the entire table into memory.",
                    "recommendation": "Always apply SETRANGE or SETFILTER before FINDSET.",
                    "example": "Table.SETRANGE(Status, Status::Active);\\nIF Table.FINDSET THEN...",
                    "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
                })

    def _detect_event_subscriber_hotspot(self, proc_name: str, proc_data: dict):
        if not proc_data.get("is_event_subscriber"): return
        
        has_loop = proc_data.get("max_loop_depth", 0) > 0
        heavy_reads = [r for r in proc_data.get("reads", []) if r["operation"] in ["FINDSET", "CALCFIELDS"]]
        
        if has_loop or heavy_reads:
            score = 150 if has_loop else 120
            severity = "critical" if has_loop else "high"
            self.bottlenecks.append({
                "pattern": "event_subscriber_hotspot",
                "severity": severity,
                "score": score,
                "procedure": proc_name,
                "explanation": "Event Subscribers run synchronously and globally. Found loops or heavy DB operations (FINDSET/CALCFIELDS) inside a subscriber, which drastically degrades entire ERP performance.",
                "recommendation": "Offload heavy processing to background tasks via JobQueue or process asynchronously. Event subscribers should exit as fast as possible.",
                "example": "IF JobQueue.ScheduleTask(...) THEN EXIT;",
                "codeunit": {"file": self.file_path.name, "object_name": self.data.get("object_name"), "object_id": self.data.get("object_id")}
            })

    def _detect_index_recommendations(self):
        """Codeunit-level pass: aggregate reads/writes per table and emit index hints."""
        READ_OPS = {"FINDSET", "FIND", "FINDFIRST", "FINDLAST", "GET"}
        WRITE_OPS = {"INSERT", "MODIFY", "DELETE", "MODIFYALL", "DELETEALL"}
        MIN_OPS = 5
        RATIO = 4

        reads_by_table: Dict[str, int] = {}
        writes_by_table: Dict[str, int] = {}

        for proc_data in self.data.get("procedures", {}).values():
            for r in proc_data.get("reads", []):
                if r.get("isTemporary") or r["operation"] not in READ_OPS:
                    continue
                table = r.get("tableName", "Unknown")
                if table and table != "Unknown":
                    reads_by_table[table] = reads_by_table.get(table, 0) + 1

            for w in proc_data.get("writes", []):
                if w.get("isTemporary") or w["operation"] not in WRITE_OPS:
                    continue
                table = w.get("tableName", "Unknown")
                if table and table != "Unknown":
                    writes_by_table[table] = writes_by_table.get(table, 0) + 1

        all_tables = set(reads_by_table) | set(writes_by_table)
        codeunit_ref = {
            "file": self.file_path.name,
            "object_name": self.data.get("object_name"),
            "object_id": self.data.get("object_id"),
        }

        for table in sorted(all_tables):
            reads = reads_by_table.get(table, 0)
            writes = writes_by_table.get(table, 0)

            if reads >= MIN_OPS and reads >= RATIO * max(writes, 1):
                severity = "medium" if reads >= 10 else "low"
                score = 30 + min(reads * 2, 20)
                self.bottlenecks.append(
                    {
                        "pattern": "missing_index_candidate",
                        "severity": severity,
                        "score": score,
                        "procedure": "(codeunit-level)",
                        "explanation": f"Table '{table}' is read {reads}x but written only {writes}x in this codeunit. A missing index may cause repeated full-table scans.",
                        "recommendation": f"Consider adding a covering index on the filter columns used when reading '{table}'. Verify with SQL Server DMVs (sys.dm_db_missing_index_details).",
                        "example": f"// Check SETRANGE/SETFILTER fields before {table}.FINDSET\n// Add index: CREATE INDEX ON [{table}] (FilterCol1, FilterCol2)",
                        "codeunit": codeunit_ref,
                    }
                )

            elif writes >= MIN_OPS and writes >= RATIO * max(reads, 1):
                severity = "low"
                score = 25 + min(writes * 2, 15)
                self.bottlenecks.append(
                    {
                        "pattern": "index_overhead",
                        "severity": severity,
                        "score": score,
                        "procedure": "(codeunit-level)",
                        "explanation": f"Table '{table}' is written {writes}x but read only {reads}x in this codeunit. Extra indexes slow down every INSERT/MODIFY/DELETE.",
                        "recommendation": f"Review existing indexes on '{table}'. Drop or defer non-essential indexes if this codeunit is a high-frequency write path.",
                        "example": f"// Audit indexes: SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('{table}')\n// DROP INDEX if rarely used for reads",
                        "codeunit": codeunit_ref,
                    }
                )
