"""
Enhanced C-AL codeunit parser (standalone, matching service implementation).
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


class CodeunitParser:
    """Enhanced parser for C/AL codeunit files matching service implementation."""

    # Reserved words to exclude from call extraction
    RESERVED_WORDS = {
        "INIT",
        "INSERT",
        "MODIFY",
        "DELETE",
        "RENAME",
        "COMMIT",
        "FINDFIRST",
        "FINDLAST",
        "FINDSET",
        "GET",
        "SETRANGE",
        "SETFILTER",
        "COPYSTR",
        "EXIT",
        "STRPOS",
        "FORMAT",
        "IF",
        "THEN",
        "ELSE",
        "BEGIN",
        "END",
        "WITH",
        "DO",
        "CASE",
        "OF",
        "REPEAT",
        "UNTIL",
        "WHILE",
        "FOR",
        "TO",
        "CLEAR",
        "ERROR",
        "MESSAGE",
        "CONFIRM",
        "CALCFIELDS",
        "CALCSUM",
        "UPPERCASE",
        "LOWERCASE",
        "STRLEN",
        "TESTFIELD",
        "VALIDATE",
        "EVALUATE",
        "ROUND",
        "ABS",
        "POWER",
    }

    # Statement keywords that indicate not a procedure definition
    STATEMENT_KEYWORDS = ["IF", "WHILE", "WITH", "CASE", "UNTIL", "FOR", "REPEAT"]

    def __init__(self, cal_path, table_metadata=None):
        cal_path = Path(cal_path)

        # Handle both .cs and .c-al inputs
        if cal_path.suffix == ".cs":
            self.cs_path = cal_path
            self.cal_path = cal_path.with_suffix(".c-al")
        elif cal_path.suffix == ".c-al":
            self.cal_path = cal_path
            self.cs_path = cal_path.with_suffix(".cs")
        else:
            self.cal_path = cal_path
            self.cs_path = None

        self.table_metadata = table_metadata or {}

        # Extracted Data
        self.object_id = None
        self.object_name = None
        self.procedures = {}
        self.dependencies = {"reports": set(), "pages": set(), "codeunits": set(), "xmlports": set(), "tables": set()}
        self.warnings = []
        self.global_variables = {}
        self.table_variables = {}
        self.temp_table_vars = set()
        self.source_code = ""

        # State during parsing
        self.current_procedure = None
        self.block_depth = 0
        self.max_nesting = 0
        self.in_with_block = False
        self.with_variable = None
        self.loop_depth = 0
        self.in_loop = False
        self._loop_stack = []
        self._pending_while_for = 0
        self.filtered_vars = set()

    @lru_cache(maxsize=None)
    def parse(self):
        """Main parsing entry point."""
        self._parse_cs_companion()
        self._parse_cal()

        return self._build_report()

    def _parse_cs_companion(self):
        """Extract metadata from .cs companion file if available."""
        if not self.cs_path or not self.cs_path.exists():
            self.warnings.append("No .cs companion file found; object metadata may be incomplete.")
            return

        try:
            with open(self.cs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Method 1: Extract from [NavCodeunit(2, "Company-Initialize")] attribute
            match = re.search(r'\[NavCodeunit\((\d+),\s*"([^"]+)"\)\]', content)
            if match:
                self.object_id = int(match.group(1))
                self.object_name = match.group(2)

            # Method 2: Extract from class name and ObjectName property
            if not self.object_id:
                class_match = re.search(r"class\s+Codeunit(\d+)\s*:\s*NavCodeunit", content)
                if class_match:
                    self.object_id = int(class_match.group(1))

            if not self.object_name:
                name_match = re.search(r'ObjectName.*?return\s*\(\s*@?"([^"]+)"\s*\);', content, re.DOTALL)
                if name_match:
                    self.object_name = name_match.group(1)

            # Extract global variables
            var_pattern = r"private\s+(\w+)\s+([a-zA-Z0-9_]+);"
            for match in re.finditer(var_pattern, content):
                var_type = match.group(1)
                var_name = match.group(2)
                self.global_variables[var_name] = var_type

            # Extract table variable mappings (Record_TableName pattern)
            table_var_pattern = r"private\s+Record_([A-Za-z0-9_]+)\s+([a-zA-Z0-9_]+);"
            for match in re.finditer(table_var_pattern, content):
                table_name = match.group(1).replace("_", " ")
                var_name = match.group(2)
                self.table_variables[var_name] = table_name
                self.global_variables[var_name] = {"type": "Record", "table": table_name}

            # Extract NavRecordHandle variables with table IDs
            self._extract_navrecord_handles(content)

            # Detect temporary table variables
            for var_name in self.global_variables.keys():
                if var_name.startswith("Temp") or var_name.startswith("temp"):
                    self.temp_table_vars.add(var_name)

        except Exception as e:
            self.warnings.append(f"Could not parse .cs companion: {str(e)}")

    def _extract_navrecord_handles(self, content: str):
        """Extract NavRecordHandle variables and map them to table names using table IDs."""
        try:
            handle_declarations = re.finditer(r"(?:public|private)\s+NavRecordHandle\s+([a-zA-Z0-9_]+);", content)
            var_names = set()
            for match in handle_declarations:
                var_names.add(match.group(1))

            if not var_names:
                return

            for var_name in var_names:
                init_pattern = rf"{re.escape(var_name)}\s*=\s*new\s+NavRecordHandle\s*\(\s*this\s*,\s*(\d+)"
                match = re.search(init_pattern, content)

                if match:
                    table_id = match.group(1)
                    table_name = self._get_table_name_by_id(table_id)

                    if table_name:
                        self.table_variables[var_name] = table_name
                        self.global_variables[var_name] = {
                            "type": "NavRecordHandle",
                            "table": table_name,
                            "id": table_id,
                        }

                        # Check if temporary table
                        temp_match = re.search(
                            rf"{re.escape(var_name)}\s*=\s*new\s+NavRecordHandle\s*\(\s*this\s*,\s*\d+\s*,\s*(true|false)",
                            content,
                        )
                        if temp_match and temp_match.group(1) == "true":
                            self.temp_table_vars.add(var_name)

        except Exception:
            pass

    def _get_table_name_by_id(self, table_id: str) -> Optional[str]:
        """Look up table name by table ID using table metadata."""
        if not self.table_metadata:
            return None

        for _, info in self.table_metadata.items():
            if info.get("id") == str(table_id):
                return info.get("name")

        return None

    def _parse_cal(self):
        """Parse the C/AL file."""
        if not self.cal_path.exists():
            self.warnings.append(f"C-AL file not found: {self.cal_path}")
            return

        try:
            lines = self._read_cal_lines()
            self._parse_procedures(lines)
        except Exception as e:
            self.warnings.append(f"Could not parse C/AL file: {str(e)}")

    def _read_cal_lines(self) -> List[str]:
        """Pre-process C/AL file to handle multi-line statements."""
        with open(self.cal_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = f.readlines()

        self.source_code = "".join(raw_lines)

        processed = []
        current_statement = ""

        for line in raw_lines:
            stripped = line.rstrip()

            if not stripped:
                if current_statement:
                    processed.append(current_statement)
                    current_statement = ""
                continue

            if stripped and stripped[0] in (" ", "\t"):
                if current_statement:
                    current_statement += " " + stripped.strip()
                else:
                    current_statement = stripped
            else:
                if current_statement:
                    processed.append(current_statement)
                current_statement = stripped

            if stripped.rstrip().endswith(";"):
                if current_statement:
                    processed.append(current_statement)
                    current_statement = ""

        if current_statement:
            processed.append(current_statement)

        return processed

    def _parse_procedures(self, lines: List[str]):
        """Parse procedures from processed lines."""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if not line.startswith((" ", "\t")):
                proc_match = self._match_procedure_definition(stripped)
                if proc_match:
                    self._start_new_procedure(proc_match)
                    continue

            if self.current_procedure:
                self._analyze_line(stripped)

    def _match_procedure_definition(self, line: str) -> Optional[Dict[str, Any]]:
        """Match and extract procedure definition metadata."""
        proc_pattern = r"^([A-Za-z][A-Za-z0-9_]*)\s*\((.*?)\)(?:\s*:\s*(.+))?$"
        match = re.match(proc_pattern, line)

        if not match:
            return None

        proc_name = match.group(1)

        if any(line.upper().startswith(kw) for kw in self.STATEMENT_KEYWORDS):
            return None

        params = match.group(2).strip() if match.group(2) else ""
        return_type = match.group(3).strip() if match.group(3) else None

        return {
            "name": proc_name,
            "params": params,
            "return_type": return_type,
        }

    def _start_new_procedure(self, proc_info: Dict[str, Any]):
        """Initialize a new procedure for tracking."""
        proc_name = proc_info["name"]
        self.current_procedure = proc_name

        self.block_depth = 0
        self.max_nesting = 0
        self.in_with_block = False
        self.with_variable = None
        self.loop_depth = 0
        self.in_loop = False
        self._loop_stack = []
        self._pending_while_for = 0
        self.filtered_vars = set()

        self.procedures[proc_name] = {
            "params": proc_info["params"],
            "returnType": proc_info["return_type"],
            "calls": [],
            "calls_in_loop": [],
            "writes": [],
            "reads": [],
            "guards": [],
            "is_event": proc_name.startswith("On"),
            "complexity": 1,
            "lines": [],
            "nesting_depth": 0,
            "max_loop_depth": 0,
            "variables": {},
        }

    def _analyze_line(self, line: str):
        """Analyze a single line of code within a procedure."""
        if not self.current_procedure:
            return

        proc_data = self.procedures[self.current_procedure]
        proc_data["lines"].append(line)

        upper_line = line.upper()

        self._track_blocks(upper_line, proc_data)
        self._track_loops(upper_line, proc_data)
        self._track_filters(upper_line)
        self._update_complexity(upper_line, proc_data)
        self._extract_dependencies(line)
        self._extract_calls(line, proc_data)
        self._detect_operations(line, proc_data)

    def _track_blocks(self, upper_line: str, proc_data: dict):
        """Track BEGIN/END blocks and WITH statements for nesting depth."""
        stripped = upper_line.strip()

        if stripped.startswith("BEGIN"):
            self.block_depth += 1
            self.max_nesting = max(self.max_nesting, self.block_depth)
            while self._pending_while_for > 0:
                self._loop_stack.append(("WHILE_FOR", self.block_depth))
                self._pending_while_for -= 1

        elif stripped in ["END;", "END"]:
            self.block_depth = max(0, self.block_depth - 1)
            while self._loop_stack and self._loop_stack[-1][0] == "WHILE_FOR" and self._loop_stack[-1][1] > self.block_depth:
                self._loop_stack.pop()
                self.loop_depth = max(0, self.loop_depth - 1)
            self.in_loop = self.loop_depth > 0
            if self.in_with_block and self.block_depth == 0:
                self.in_with_block = False
                self.with_variable = None

        with_match = re.search(r"WITH\s+([A-Za-z0-9_]+)\s+DO", upper_line)
        if with_match:
            self.with_variable = with_match.group(1)
            self.in_with_block = True

        proc_data["nesting_depth"] = max(proc_data.get("nesting_depth", 0), self.block_depth)

    _STREAM_PATTERN = re.compile(r"\b(?:IN|OUT)?STREAM\b|\.EOS\b", re.IGNORECASE)

    def _track_loops(self, upper_line: str, proc_data: dict):
        """Track loop entry/exit for context-aware analysis."""
        if re.search(r"\bREPEAT\b", upper_line):
            self.loop_depth += 1
            self.in_loop = True
            self._loop_stack.append(("REPEAT", self.block_depth))

        if re.search(r"\b(WHILE|FOR)\b", upper_line) and not self._STREAM_PATTERN.search(upper_line):
            self.loop_depth += 1
            self.in_loop = True
            if re.search(r"\bBEGIN\b", upper_line):
                self._loop_stack.append(("WHILE_FOR", self.block_depth))
            else:
                self._pending_while_for += 1

        if re.search(r"\bUNTIL\b", upper_line):
            for i in range(len(self._loop_stack) - 1, -1, -1):
                if self._loop_stack[i][0] == "REPEAT":
                    self._loop_stack.pop(i)
                    break
            self.loop_depth = max(0, self.loop_depth - 1)
            self.in_loop = self.loop_depth > 0

        proc_data["max_loop_depth"] = max(proc_data.get("max_loop_depth", 0), self.loop_depth)

    def _track_filters(self, upper_line: str):
        """Track SETRANGE/SETFILTER to know if subsequent operations are filtered."""
        filter_pattern = r"([A-Za-z0-9_]+)\.(?:SETRANGE|SETFILTER)\s*\("
        match = re.search(filter_pattern, upper_line)
        if match:
            self.filtered_vars.add(match.group(1))

        reset_pattern = r"([A-Za-z0-9_]+)\.RESET"
        match = re.search(reset_pattern, upper_line)
        if match:
            self.filtered_vars.discard(match.group(1))

    def _update_complexity(self, upper_line: str, proc_data: dict):
        """Calculate cyclomatic complexity."""
        if re.search(r"\bIF\b", upper_line):
            proc_data["complexity"] += 1
        if re.search(r"\bCASE\b", upper_line):
            proc_data["complexity"] += 1
        if re.search(r"\bFOR\b", upper_line):
            proc_data["complexity"] += 1
        if re.search(r"\bWHILE\b", upper_line):
            proc_data["complexity"] += 1
        if re.search(r"\bREPEAT\b", upper_line):
            proc_data["complexity"] += 1

        proc_data["complexity"] += upper_line.count(" AND ")
        proc_data["complexity"] += upper_line.count(" OR ")

    def _extract_dependencies(self, line: str):
        """Extract dependency references."""
        patterns = {
            "reports": re.compile(r'REPORT::(?:"([^"]+)"|([A-Za-z0-9_]+))'),
            "pages": re.compile(r'PAGE::(?:"([^"]+)"|([A-Za-z0-9_]+))'),
            "codeunits": re.compile(r'CODEUNIT::(?:"([^"]+)"|([A-Za-z0-9_]+))'),
            "xmlports": re.compile(r'XMLPORT::(?:"([^"]+)"|([A-Za-z0-9_]+))'),
        }

        for dep_type, pattern in patterns.items():
            for match in pattern.finditer(line):
                dep_name = match.group(1) if match.group(1) else match.group(2)
                if dep_name:
                    self.dependencies[dep_type].add(dep_name)

    def _extract_calls(self, line: str, proc_data: dict):
        """Extract function/method calls."""
        obj_method_pattern = r"([A-Z][A-Za-z0-9_]+)\.([A-Z][A-Za-z0-9_]+)\s*(?:\(|;)"
        for match in re.finditer(obj_method_pattern, line):
            obj_name = match.group(1)
            method_name = match.group(2)

            if method_name.upper() not in self.RESERVED_WORDS:
                full_call = f"{obj_name}.{method_name}"
                if full_call not in proc_data["calls"]:
                    proc_data["calls"].append(full_call)
                if self.in_loop and full_call not in proc_data["calls_in_loop"]:
                    proc_data["calls_in_loop"].append(full_call)

        method_pattern = r"\b([A-Z][A-Za-z0-9_]+)\s*(?:\(|(?=;))"
        for match in re.finditer(method_pattern, line):
            method_name = match.group(1)

            if method_name.upper() not in self.RESERVED_WORDS:
                start_pos = match.start()
                if start_pos > 0 and line[start_pos - 1] == ".":
                    continue

                if method_name not in proc_data["calls"]:
                    if not any(call.endswith(f".{method_name}") for call in proc_data["calls"]):
                        proc_data["calls"].append(method_name)
                if self.in_loop and method_name not in proc_data["calls_in_loop"]:
                    if not any(c.endswith(f".{method_name}") for c in proc_data["calls_in_loop"]):
                        proc_data["calls_in_loop"].append(method_name)

    def _detect_operations(self, line: str, proc_data: dict):
        """Detect write operations and guard patterns."""
        upper_line = line.upper()

        self._detect_guards(upper_line, proc_data)
        self._detect_reads(line, upper_line, proc_data)
        self._detect_writes(line, upper_line, proc_data)

    def _detect_guards(self, upper_line: str, proc_data: dict):
        """Detect guard patterns."""
        guard_patterns = [
            (r"IF\s+NOT\s+([A-Za-z0-9_]+)\.FINDFIRST", "IF NOT FINDFIRST"),
            (r"IF\s+NOT\s+([A-Za-z0-9_]+)\.GET\s*\(", "IF NOT GET"),
            (r"IF\s+([A-Za-z0-9_]+)\.FINDFIRST", "IF FINDFIRST"),
            (r"IF\s+([A-Za-z0-9_]+)\.GET\s*\(", "IF GET"),
            (r"IF\s+([A-Za-z0-9_]+)\.ISEMPTY", "IF ISEMPTY"),
            (r"IF\s+NOT\s+([A-Za-z0-9_]+)\.ISEMPTY", "IF NOT ISEMPTY"),
        ]

        for pattern, guard_type in guard_patterns:
            match = re.search(pattern, upper_line)
            if match:
                table_var = match.group(1)
                guard_info = {"type": guard_type, "table": table_var}
                proc_data["guards"].append(guard_info)
                break

    def _is_temporary_table(self, var_name: str) -> bool:
        """Check if a variable is a temporary table."""
        return (
            var_name in self.temp_table_vars
            or var_name.upper().startswith("TEMP")
            or var_name.upper().startswith("TMP")
        )

    def _get_table_name(self, var_name: str) -> str:
        """Get the table name for a variable."""
        if var_name in self.table_variables:
            return self.table_variables[var_name]

        var_name_lower = var_name.lower()
        for key, value in self.table_variables.items():
            if key.lower() == var_name_lower:
                return value

        return "Unknown"

    def _detect_reads(self, line: str, upper_line: str, proc_data: dict):
        """Detect read operations with metadata."""
        read_ops = {
            "FINDSET": r"([A-Za-z0-9_]+)\.FINDSET(?:\s*\(\s*(TRUE|FALSE)?\s*\))?",
            "FINDFIRST": r"([A-Za-z0-9_]+)\.FINDFIRST",
            "FINDLAST": r"([A-Za-z0-9_]+)\.FINDLAST",
            "FIND": r"([A-Za-z0-9_]+)\.FIND\s*\(\s*'([^']+)'\s*\)",
            "GET": r"([A-Za-z0-9_]+)\.GET\s*\(",
            "CALCFIELDS": r"([A-Za-z0-9_]+)\.CALCFIELDS\s*\(",
            "CALCSUMS": r"([A-Za-z0-9_]+)\.CALCSUMS\s*\(",
            "SETRANGE": r"([A-Za-z0-9_]+)\.SETRANGE\s*\(",
            "SETFILTER": r"([A-Za-z0-9_]+)\.SETFILTER\s*\(",
        }

        for op, pattern in read_ops.items():
            match = re.search(pattern, upper_line)
            if match:
                table_var = match.group(1)
                has_filter = table_var in self.filtered_vars
                is_temp = self._is_temporary_table(table_var)
                table_name = self._get_table_name(table_var)

                op_entry = {
                    "operation": op,
                    "tableVar": table_var,
                    "tableName": table_name,
                    "isTemporary": is_temp,
                    "inLoop": self.in_loop,
                    "loopDepth": self.loop_depth,
                    "hasFilter": has_filter,
                    "line": line.strip(),
                }
                proc_data["reads"].append(op_entry)

                if table_name != "Unknown" and not is_temp:
                    self.dependencies["tables"].add(table_name)

                break

    def _detect_writes(self, line: str, upper_line: str, proc_data: dict):
        """Detect write operations with metadata."""
        write_ops = {
            "INSERT": r"([A-Za-z0-9_]+)\.INSERT(?:\s*\(\s*(TRUE|FALSE)?\s*\))?",
            "MODIFY": r"([A-Za-z0-9_]+)\.MODIFY(?:\s*\(\s*(TRUE|FALSE)?\s*\))?",
            "DELETE": r"([A-Za-z0-9_]+)\.DELETE(?:\s*\(\s*(TRUE|FALSE)?\s*\))?",
            "RENAME": r"([A-Za-z0-9_]+)\.RENAME\s*\(",
            "MODIFYALL": r"([A-Za-z0-9_]+)\.MODIFYALL\s*\(",
            "DELETEALL": r"([A-Za-z0-9_]+)\.DELETEALL",
            "COMMIT": r"\bCOMMIT\b",
        }

        for op, pattern in write_ops.items():
            match = re.search(pattern, upper_line)
            if match:
                if op == "COMMIT":
                    op_entry = {
                        "operation": op,
                        "tableVar": None,
                        "tableName": None,
                        "isTemporary": False,
                        "guard": None,
                        "runTrigger": False,
                        "line": line.strip(),
                    }
                    proc_data["writes"].append(op_entry)
                    continue

                table_var = match.group(1)

                run_trigger = True
                if match.lastindex and match.lastindex >= 2 and match.group(2):
                    run_trigger = match.group(2).upper() == "TRUE"
                elif op in ["MODIFYALL", "DELETEALL"]:
                    run_trigger = False

                guard = proc_data["guards"][-1] if proc_data["guards"] else None
                is_temp = self._is_temporary_table(table_var)
                table_name = self._get_table_name(table_var)

                op_entry = {
                    "operation": op,
                    "tableVar": table_var,
                    "tableName": table_name,
                    "isTemporary": is_temp,
                    "guard": guard,
                    "runTrigger": run_trigger,
                    "line": line.strip(),
                }
                proc_data["writes"].append(op_entry)

                if table_name != "Unknown" and not is_temp:
                    self.dependencies["tables"].add(table_name)

    def _build_report(self):
        """Build the final analysis report."""
        # Calculate total complexity
        total_complexity = sum(p.get("complexity", 1) for p in self.procedures.values())

        # Collect side effects
        side_effects = []
        for proc_name, data in self.procedures.items():
            for write in data["writes"]:
                side_effects.append(
                    {
                        "operation": write["operation"],
                        "tableVar": write.get("tableVar"),
                        "tableName": write.get("tableName"),
                        "isTemporary": write.get("isTemporary", False),
                        "guard": write.get("guard"),
                        "runTrigger": write.get("runTrigger", True),
                        "line": write["line"],
                        "procedure": proc_name,
                    }
                )

        return {
            "object_id": self.object_id,
            "object_name": self.object_name,
            "complexity_score": total_complexity,
            "procedures": self.procedures,
            "side_effects": side_effects,
            "dependencies": {
                "tables": list(self.dependencies["tables"]),
                "codeunits": list(self.dependencies["codeunits"]),
                "reports": list(self.dependencies["reports"]),
                "pages": list(self.dependencies["pages"]),
                "xmlports": list(self.dependencies["xmlports"]),
            },
            "warnings": self.warnings,
            "source_code": self.source_code,
            "tableVariables": dict(self.table_variables),
            "temporaryTables": list(self.temp_table_vars),
        }
