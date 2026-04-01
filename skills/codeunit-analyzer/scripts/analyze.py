#!/usr/bin/env python3
"""C-AL codeunit, table, and page analyzer.

Sub-commands:
  list                 – list all available .cs/.c-al files
  analyze <file>       – deep-dive into one file
  scan                 – project-wide bottleneck scan
  optimize <file>      – phased optimization suggestions
  setloadfields        – dedicated SETLOADFIELDS / SELECT-* audit
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from detector import BottleneckDetector
from helpers import run_in_processpool
from parser import CodeunitParser
from table_metadata import TableMetadataLoader


def get_project_dirs():
    import os
    env_dir = os.environ.get("CODEUNITS_DIR")
    if env_dir:
        base_dir = Path(env_dir).parent
        return Path(env_dir), base_dir / "tables", base_dir / "pages"
    else:
        # __file__ is in scripts/analyze.py
        data_dir = Path(__file__).parent.parent.parent.parent / "data"
        return data_dir / "codeunits", data_dir / "tables", data_dir / "pages"


def _parse_codeunit_file(file, source_type="unknown", table_metadata=None):
    try:
        parser = CodeunitParser(file, table_metadata=table_metadata)
        data = parser.parse()
        return {
            "path": file,
            "name": file.name,
            "object_name": data.get("object_name", "Unknown"),
            "object_id": data.get("object_id", "N/A"),
            "source_type": source_type,
        }

    except Exception:
        return {"path": file, "name": file.name, "object_name": "Error parsing", "object_id": "N/A", "source_type": source_type}


def list_codeunits():
    codeunits_dir, tables_dir, pages_dir = get_project_dirs()

    tagged_files = []
    if codeunits_dir.exists():
        for f in list(codeunits_dir.rglob("*.cs")) + list(codeunits_dir.rglob("*.c-al")):
            tagged_files.append((f, "codeunit"))
    if tables_dir.exists():
        for f in list(tables_dir.rglob("*.cs")) + list(tables_dir.rglob("*.c-al")):
            tagged_files.append((f, "table"))
    if pages_dir.exists():
        for f in list(pages_dir.rglob("*.cs")) + list(pages_dir.rglob("*.c-al")):
            tagged_files.append((f, "page"))

    if not tagged_files:
        return []

    table_metadata = TableMetadataLoader.load_metadata()
    results = run_in_processpool(_parse_codeunit_file, ((f, st, table_metadata) for f, st in tagged_files), desc="Listing")
    return sorted(results, key=lambda x: x["name"])


def analyze_codeunit(filename, table_metadata=None):
    codeunits_dir, tables_dir, pages_dir = get_project_dirs()
    file_path = Path(filename)
    if not file_path.exists():
        found = False
        for search_dir in [codeunits_dir, tables_dir, pages_dir]:
            if search_dir.exists():
                matches = list(search_dir.rglob(str(filename)))
                if matches:
                    file_path = matches[0]
                    found = True
                    break
        if not found:
            raise FileNotFoundError(f"File not found: {filename}")

    if table_metadata is None:
        table_metadata = TableMetadataLoader.load_metadata()

    parser = CodeunitParser(file_path, table_metadata=table_metadata)
    data = parser.parse()

    detector = BottleneckDetector(data, file_path, table_metadata=table_metadata)
    bottlenecks = detector.detect()

    return {"object": data, "bottlenecks": bottlenecks}


def _analyze_codeunit_for_scan(file_info, table_metadata):
    try:
        # Pass the absolute path to analyze_codeunit so it doesn't need to re-rglob it
        result = analyze_codeunit(file_info["path"], table_metadata=table_metadata)
        bottlenecks = []

        for b in result["bottlenecks"]:
            b["codeunit"]["file"] = file_info["name"]
            bottlenecks.append(b)

        return bottlenecks

    except Exception as e:
        print(f"Error analyzing {file_info['name']}: {e}", file=sys.stderr)
        return []


def scan_all_bottlenecks():
    files = list_codeunits()
    table_metadata = TableMetadataLoader.load_metadata()
    results = run_in_processpool(_analyze_codeunit_for_scan, ((f, table_metadata) for f in files), desc="Scanning")
    all_bottlenecks = [b for bottlenecks in results for b in bottlenecks]
    all_bottlenecks.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_bottlenecks


def format_severity_badge(severity):
    badges = {
        "critical": "[CRITICAL]",
        "high": "[HIGH]",
        "medium": "[MEDIUM]",
        "low": "[LOW]",
    }
    return badges.get(severity, "[" + severity.upper() + "]")


def format_bottleneck(bottleneck, index):
    pattern = bottleneck.get("pattern", "unknown").replace("_", " ").title()
    severity = format_severity_badge(bottleneck.get("severity", "low"))
    procedure = bottleneck.get("procedure", "N/A")
    score = bottleneck.get("score", 0)
    explanation = bottleneck.get("explanation", "")
    recommendation = bottleneck.get("recommendation", "")

    output = [
        f"\n{'=' * 80}",
        f"[{index + 1}] {severity} - {pattern}",
        f"{'=' * 80}",
        f"Procedure: {procedure}",
        f"Score: {score} points",
        "\nIssue:",
        f"  {explanation}",
    ]

    if recommendation:
        output.extend(["\nRecommendation:", f"  {recommendation}"])

    if bottleneck.get("example"):
        output.extend(["\nCode Example:", f"  {bottleneck['example']}"])

    return "\n".join(output)


def cmd_list():
    print("Fetching codeunits...\n")

    files = list_codeunits()

    if not files:
        codeunits_dir, tables_dir, pages_dir = get_project_dirs()
        print("No codeunits, tables, or pages found.")
        print(f"Expected directories: {codeunits_dir}, {tables_dir}, or {pages_dir}")
        return 1

    print(f"Found {len(files)} codeunits:\n")
    print(f"{'File':<20} {'Object Name':<50} {'ID':<10}")
    print("=" * 120)

    for file_info in files:
        name = file_info["name"]
        obj_name = file_info["object_name"] or "Unknown"
        obj_id = file_info["object_id"] or "N/A"
        print(f"{name:<20} {obj_name:<50} {obj_id:<10}")

    return 0


def cmd_analyze(filename, with_ai=False):
    print(f"Analyzing {filename}...\n")

    try:
        result = analyze_codeunit(filename)

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nRun 'python .skills/codeunit-analyzer/analyze.py list' to see available files.")
        return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1

    obj = result["object"]
    bottlenecks = result["bottlenecks"]

    print("=" * 80)
    print(f"CODEUNIT: {obj.get('object_name', 'Unknown')}")
    print("=" * 80)
    print(f"ID: {obj.get('object_id', 'N/A')}")
    print(f"Procedures: {len(obj.get('procedures', {}))}")
    print(f"File: {filename}")

    if bottlenecks:
        print(f"\n\n{'=' * 80}")
        print(f"PERFORMANCE BOTTLENECKS ({len(bottlenecks)} issues)")
        print(f"{'=' * 80}")

        critical = [b for b in bottlenecks if b.get("severity") == "critical"]
        high = [b for b in bottlenecks if b.get("severity") == "high"]
        medium = [b for b in bottlenecks if b.get("severity") == "medium"]
        low = [b for b in bottlenecks if b.get("severity") == "low"]

        print(f"\nCritical: {len(critical)}")
        print(f"High: {len(high)}")
        print(f"Medium: {len(medium)}")
        print(f"Low: {len(low)}")

        for idx, bottleneck in enumerate(bottlenecks):
            print(format_bottleneck(bottleneck, idx))

    else:
        print("\n[OK] No performance bottlenecks detected!")

    deps = obj.get("dependencies", {})
    if deps.get("tables"):
        print(f"\n\n{'=' * 80}")
        print("DEPENDENCIES")
        print(f"{'=' * 80}")
        print(f"\nTables ({len(deps['tables'])}):")
        for table in deps["tables"]:
            print(f"  - {table}")

    if with_ai:
        print(f"\n\n{'=' * 80}")
        print("AI EXPLANATION")
        print(f"{'=' * 80}\n")
        print("AI explanations require Azure OpenAI configuration.")
        print("Set environment variables: AZURE_ENDPOINT, AZURE_API_KEY, AZURE_DEPLOYMENT")

    return 0


def cmd_scan(output_file=None, limit: int | None = 25):
    print("Scanning all codeunits for performance bottlenecks...\n")

    files = list_codeunits()

    if not files:
        print("No codeunits or tables found.")
        return 1

    print(f"Analyzing {len(files)} codeunits...\n")

    all_bottlenecks = scan_all_bottlenecks()

    print("=" * 80)
    print("BOTTLENECK SCAN SUMMARY")
    print("=" * 80)
    print(f"Total Issues: {len(all_bottlenecks)}")

    critical = [b for b in all_bottlenecks if b.get("severity") == "critical"]
    high = [b for b in all_bottlenecks if b.get("severity") == "high"]
    medium = [b for b in all_bottlenecks if b.get("severity") == "medium"]
    low = [b for b in all_bottlenecks if b.get("severity") == "low"]

    print(f"  Critical: {len(critical)}")
    print(f"  High: {len(high)}")
    print(f"  Medium: {len(medium)}")
    print(f"  Low: {len(low)}")

    by_codeunit = {}
    for b in all_bottlenecks:
        file = b.get("codeunit", {}).get("file") or "Unknown"
        name = b.get("codeunit", {}).get("object_name") or file
        obj_id = b.get("codeunit", {}).get("object_id") or "N/A"

        if file not in by_codeunit:
            by_codeunit[file] = {
                "name": name,
                "object_id": obj_id,
                "bottlenecks": [],
                "total_score": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }

        by_codeunit[file]["bottlenecks"].append(b)
        by_codeunit[file]["total_score"] += b.get("score", 0)
        severity = b.get("severity", "low")

        if severity == "critical":
            by_codeunit[file]["critical"] += 1
        elif severity == "high":
            by_codeunit[file]["high"] += 1
        elif severity == "medium":
            by_codeunit[file]["medium"] += 1
        elif severity == "low":
            by_codeunit[file]["low"] += 1

    sorted_codeunits = sorted(by_codeunit.items(), key=lambda x: x[1]["total_score"], reverse=True)

    if limit:
        sorted_codeunits = sorted_codeunits[:limit]

    print("\n" + "=" * 80)
    print(f"CODEUNITS BY PERFORMANCE IMPACT (showing top {len(sorted_codeunits)})")
    print("=" * 80 + "\n")

    print("| Rank | Codeunit Name | File | Object ID | Total Score | Issues | Critical | High | Medium | Low |")
    print("|------|---------------|------|-----------|-------------|--------|----------|------|--------|-----|")

    for idx, (file, data) in enumerate(sorted_codeunits, 1):
        name_str = str(data["name"])
        name = name_str[:40] + "..." if len(name_str) > 40 else name_str
        file_display = str(file)[:25] + "..." if len(str(file)) > 25 else str(file)
        obj_id = str(data["object_id"])
        total_score = data["total_score"]
        total_issues = len(data["bottlenecks"])
        critical_count = data["critical"]
        high_count = data["high"]
        medium_count = data["medium"]
        low_count = data["low"]

        print(
            f"| {idx} | {name} | {file_display} | {obj_id} | {total_score} | {total_issues} | {critical_count} | {high_count} | {medium_count} | {low_count} |"
        )

    print(f"\n{'=' * 80}")
    print("SUMMARY STATISTICS")
    print("=" * 80)

    total_score = sum(data["total_score"] for _, data in sorted_codeunits)
    total_issues = sum(len(data["bottlenecks"]) for _, data in sorted_codeunits)
    total_critical = sum(data["critical"] for _, data in sorted_codeunits)
    total_high = sum(data["high"] for _, data in sorted_codeunits)
    total_medium = sum(data["medium"] for _, data in sorted_codeunits)
    total_low = sum(data["low"] for _, data in sorted_codeunits)

    print(f"Codeunits shown: {len(sorted_codeunits)}")
    print(f"Total score: {total_score} points")
    print(f"Total issues: {total_issues}")
    print(f"  Critical: {total_critical}")
    print(f"  High: {total_high}")
    print(f"  Medium: {total_medium}")
    print(f"  Low: {total_low}")

    print("\n[INFO] Use --output <file.json> to save detailed bottleneck information")
    print("[INFO] Use 'analyze <filename>' to see detailed bottlenecks for a specific codeunit")

    if output_file:
        output_data = []
        for file, data in sorted_codeunits:
            output_data.append(
                {
                    "codeunit": {"file": file, "name": data["name"], "object_id": data["object_id"]},
                    "total_score": data["total_score"],
                    "issue_counts": {
                        "critical": data["critical"],
                        "high": data["high"],
                        "medium": data["medium"],
                        "low": data["low"],
                    },
                    "bottlenecks": sorted(data["bottlenecks"], key=lambda x: x.get("score", 0), reverse=True),
                }
            )

        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"\n\nFull report saved to: {output_file}")

    return 0


def cmd_optimize(filename):
    print(f"Generating optimization plan for {filename}...\n")

    try:
        result = analyze_codeunit(filename)

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1

    obj = result["object"]
    bottlenecks = result["bottlenecks"]

    if not bottlenecks:
        print("[OK] No bottlenecks detected - this codeunit is already optimized!")
        return 0

    print("=" * 80)
    print(f"OPTIMIZATION PLAN: {obj.get('object_name', 'Unknown')}")
    print("=" * 80)
    print(f"Total Bottlenecks: {len(bottlenecks)}")

    critical = [b for b in bottlenecks if b.get("severity") == "critical"]
    high = [b for b in bottlenecks if b.get("severity") == "high"]
    medium = [b for b in bottlenecks if b.get("severity") == "medium"]

    total_score = sum(b.get("score", 0) for b in bottlenecks)
    print(f"Total Score: {total_score} points")
    print(f"\n  Critical: {len(critical)}")
    print(f"  High: {len(high)}")
    print(f"  Medium: {len(medium)}")

    if critical:
        print(f"\n\n{'=' * 80}")
        print("PHASE 1: CRITICAL FIXES (Do First)")
        print(f"{'=' * 80}")

        for idx, bottleneck in enumerate(critical, 1):
            pattern = bottleneck.get("pattern", "").replace("_", " ").title()
            print(f"\n{idx}. Fix {pattern}")
            print(f"   Procedure: {bottleneck.get('procedure', 'Unknown')}")
            print(f"   Score: {bottleneck.get('score', 0)} points")
            print(f"   Issue: {bottleneck.get('explanation', '')}")
            print(f"   Fix: {bottleneck.get('recommendation', '')}")

            if bottleneck.get("example"):
                print("\n   Code Example:")
                for line in bottleneck["example"].split("\n"):
                    print(f"     {line}")

    if high:
        print(f"\n\n{'=' * 80}")
        print("PHASE 2: HIGH PRIORITY FIXES (Do Next)")
        print(f"{'=' * 80}")

        for idx, bottleneck in enumerate(high, 1):
            pattern = bottleneck.get("pattern", "").replace("_", " ").title()
            print(f"\n{idx}. Fix {pattern}")
            print(f"   Procedure: {bottleneck.get('procedure', 'Unknown')}")
            print(f"   Score: {bottleneck.get('score', 0)} points")
            print(f"   Fix: {bottleneck.get('recommendation', '')}")

    print(f"\n\n{'=' * 80}")
    print("RECOMMENDATIONS")
    print(f"{'=' * 80}\n")

    if critical:
        print("1. IMMEDIATE ACTION (Critical):")
        for b in critical[:3]:
            pattern = b.get("pattern", "").replace("_", " ").title()
            print(f"   - Fix {pattern} in {b.get('procedure', 'Unknown')}")

    if high:
        print("\n2. SHORT TERM (High Priority):")
        for b in high[:3]:
            pattern = b.get("pattern", "").replace("_", " ").title()
            print(f"   - Fix {pattern} in {b.get('procedure', 'Unknown')}")

    if medium:
        print("\n3. MEDIUM TERM (Backlog):")
        for b in medium[:3]:
            pattern = b.get("pattern", "").replace("_", " ").title()
            print(f"   - Fix {pattern} in {b.get('procedure', 'Unknown')}")

    critical_score = sum(b.get("score", 0) for b in critical)
    high_score = sum(b.get("score", 0) for b in high)

    if critical_score + high_score > 0:
        print(f"\n\n{'=' * 80}")
        print("ESTIMATED IMPACT")
        print(f"{'=' * 80}")
        print(f"Fixing critical + high issues: {critical_score + high_score} points reduction")
        print("Estimated performance gain: 60-80% improvement on affected operations")

    return 0


# ---------------------------------------------------------------------------
# SETLOADFIELDS sub-command
# ---------------------------------------------------------------------------

def _compute_setloadfields_urgency(read: Dict[str, Any], table_info: Dict[str, Any]) -> int:
    """Compute a per-read urgency score for a missing SETLOADFIELDS.

    Factors:
      - Base                    40 pts   (any read without SETLOADFIELDS costs something)
      - Loop penalty           +20 pts   (fired once per iteration → N× cost)
      - Row impact multiplier  ×row_mult (large tables → more data on wire)
      - Column width multiplier×col_mult (wide tables → more bytes per row)
      - FlowField bonus        +15 pts   (without SETLOADFIELDS BC calculates ALL FlowFields)
    """
    base = 40
    loop_bonus = 20 if read.get("inLoop") else 0
    flow_bonus = 15 if table_info.get("hasFlowFields") else 0

    row_mult = table_info.get("impactMultiplier", 1.0)
    col_mult = table_info.get("columnWidthMultiplier", 1.0)

    score = int((base + loop_bonus) * row_mult * col_mult + flow_bonus)
    return score


def _audit_setloadfields_in_file(file_path: Path, table_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse one file and return a list of SETLOADFIELDS audit findings."""
    try:
        parser = CodeunitParser(file_path, table_metadata=table_metadata)
        data = parser.parse()
    except Exception as e:
        return []

    READ_OPS = {"FINDSET", "FINDFIRST", "FIND", "FINDLAST", "GET"}
    findings: List[Dict[str, Any]] = []

    for proc_name, proc_data in data.get("procedures", {}).items():
        for read in proc_data.get("reads", []):
            if read.get("isTemporary"):
                continue
            if read.get("operation") not in READ_OPS:
                continue
            if read.get("hasLoadFields"):
                continue  # already has SETLOADFIELDS — no issue

            table_name = read.get("tableName", "Unknown")
            normalized = table_name.lower().strip()
            table_info = table_metadata.get(normalized, {})

            urgency = _compute_setloadfields_urgency(read, table_info)

            field_count = table_info.get("fieldCount", 0)
            col_category = table_info.get("columnWidthCategory", "unknown")
            row_info = table_info.get("friendlySize", "unknown size")
            in_loop = read.get("inLoop", False)
            has_ff = table_info.get("hasFlowFields", False)

            reasons: List[str] = []
            if in_loop:
                reasons.append("inside loop (×N cost)")
            if has_ff:
                reasons.append("table has FlowFields (BC calculates ALL on SELECT *)")
            if field_count > 30:
                reasons.append(f"wide table ({field_count} fields, {col_category})")
            if not reasons:
                reasons.append("unnecessary SELECT * overhead")

            # Build a concrete fix example with field placeholders
            example = (
                f"// Before (loads ALL {field_count or '?'} columns):\n"
                f"// {read['operation']} on {table_name}\n\n"
                f"// After (load only what you need):\n"
                f"{table_name}.SETLOADFIELDS(Field1, Field2);\n"
                f"IF {table_name}.{read['operation']} THEN ..."
            )

            findings.append({
                "pattern": "missing_setloadfields",
                "urgency": urgency,
                "procedure": proc_name,
                "operation": read["operation"],
                "table_name": table_name,
                "in_loop": in_loop,
                "has_flow_fields": has_ff,
                "field_count": field_count,
                "column_category": col_category,
                "row_info": row_info,
                "reasons": reasons,
                "example": example,
                "line": read.get("line"),
                "codeunit": {
                    "file": file_path.name,
                    "object_name": data.get("object_name"),
                    "object_id": data.get("object_id"),
                },
            })

    return findings


def _audit_file_wrapper(file_info: Dict[str, Any], table_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings = _audit_setloadfields_in_file(file_info["path"], table_metadata)
    for f in findings:
        f["codeunit"]["file"] = file_info["name"]
    return findings


def _aggregate_by_table(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group findings by table name and compute aggregate urgency per table."""
    by_table: Dict[str, Dict[str, Any]] = {}
    for f in findings:
        table = f["table_name"]
        if table not in by_table:
            by_table[table] = {
                "table_name": table,
                "total_urgency": 0,
                "occurrences": 0,
                "in_loop_count": 0,
                "has_flow_fields": f["has_flow_fields"],
                "field_count": f["field_count"],
                "column_category": f["column_category"],
                "row_info": f["row_info"],
                "affected_files": set(),
                "affected_procedures": [],
            }
        by_table[table]["total_urgency"] += f["urgency"]
        by_table[table]["occurrences"] += 1
        if f["in_loop"]:
            by_table[table]["in_loop_count"] += 1
        by_table[table]["affected_files"].add(f["codeunit"]["file"])
        by_table[table]["affected_procedures"].append(f"{f['codeunit']['file']}::{f['procedure']}")

    # Convert sets to sorted lists for JSON serialisation
    result = []
    for entry in by_table.values():
        entry["affected_files"] = sorted(entry["affected_files"])
        result.append(entry)

    result.sort(key=lambda x: x["total_urgency"], reverse=True)
    return result


def _print_setloadfields_report(findings: List[Dict[str, Any]], top: int | None) -> None:
    """Print a human-readable SETLOADFIELDS audit report."""
    if not findings:
        print("\n[OK] No missing SETLOADFIELDS detected!")
        return

    by_table = _aggregate_by_table(findings)
    if top:
        by_table = by_table[:top]

    total_score = sum(f["urgency"] for f in findings)
    loop_issues = sum(1 for f in findings if f["in_loop"])
    ff_issues = sum(1 for f in findings if f["has_flow_fields"])

    print("=" * 80)
    print("SETLOADFIELDS AUDIT — SELECT * OVERHEAD REPORT")
    print("=" * 80)
    print(f"Total missing SETLOADFIELDS : {len(findings)}")
    print(f"  Inside loops              : {loop_issues}  (highest priority — fired once per row)")
    print(f"  On FlowField tables       : {ff_issues}  (BC calculates all FlowFields without SETLOADFIELDS)")
    print(f"Total urgency score         : {total_score}")
    print()

    print("=" * 80)
    print(f"TABLES RANKED BY URGENCY (showing top {len(by_table)})")
    print("=" * 80)
    print()
    print(f"{'Rank':<5} {'Table':<35} {'Urgency':>8} {'Occ':>5} {'InLoop':>7} {'Fields':>7} {'Width':<12} {'Rows'}")
    print("-" * 110)

    for rank, entry in enumerate(by_table, 1):
        table = entry["table_name"][:33]
        urgency = entry["total_urgency"]
        occ = entry["occurrences"]
        in_loop = entry["in_loop_count"]
        fields = entry["field_count"] or "?"
        col_cat = entry["column_category"][:10]
        rows = entry["row_info"][:30]
        print(f"{rank:<5} {table:<35} {urgency:>8} {occ:>5} {in_loop:>7} {str(fields):>7} {col_cat:<12} {rows}")

    print()
    print("=" * 80)
    print("TOP INDIVIDUAL FINDINGS (sorted by urgency)")
    print("=" * 80)

    top_findings = sorted(findings, key=lambda x: x["urgency"], reverse=True)[:10]
    for idx, f in enumerate(top_findings, 1):
        line_info = f" (line {f['line']})" if f.get("line") else ""
        print(f"\n[{idx}] Urgency {f['urgency']} — {f['table_name']} · {f['operation']}{line_info}")
        print(f"     File      : {f['codeunit']['file']}")
        print(f"     Procedure : {f['procedure']}")
        print(f"     Why urgent: {', '.join(f['reasons'])}")
        print(f"     Fix:")
        for line in f["example"].split("\n"):
            print(f"       {line}")


def cmd_setloadfields(filename: str | None, top: int | None, output_file: str | None, as_json: bool) -> int:
    """Run the SETLOADFIELDS / SELECT-* audit.

    When *filename* is given, audit only that file.
    Otherwise scan the entire project.
    """
    table_metadata = TableMetadataLoader.load_metadata()

    if filename:
        # Single-file mode
        print(f"SETLOADFIELDS audit for {filename}...\n")
        codeunits_dir, tables_dir, pages_dir = get_project_dirs()
        file_path = Path(filename)
        if not file_path.exists():
            for search_dir in [codeunits_dir, tables_dir, pages_dir]:
                if search_dir.exists():
                    matches = list(search_dir.rglob(str(filename)))
                    if matches:
                        file_path = matches[0]
                        break
        if not file_path.exists():
            print(f"Error: File not found: {filename}")
            return 1

        findings = _audit_setloadfields_in_file(file_path, table_metadata)

    else:
        # Project-wide scan
        print("Scanning all codeunits for missing SETLOADFIELDS...\n")
        files = list_codeunits()
        if not files:
            print("No codeunits or tables found.")
            return 1
        print(f"Auditing {len(files)} files...\n")
        results = run_in_processpool(_audit_file_wrapper, ((f, table_metadata) for f in files), desc="SETLOADFIELDS audit")
        findings = [item for sublist in results for item in sublist]

    findings.sort(key=lambda x: x["urgency"], reverse=True)

    if as_json:
        print(json.dumps(findings, indent=2))
    else:
        _print_setloadfields_report(findings, top)

    if output_file:
        with open(output_file, "w") as fh:
            json.dump(findings, fh, indent=2)
        print(f"\nFull findings saved to: {output_file}")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Analyze C-AL codeunits for performance issues")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("list", help="List all available codeunits")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a specific codeunit")
    analyze_parser.add_argument("filename", help="Codeunit filename (e.g., 1.cs)")

    scan_parser = subparsers.add_parser("scan", help="Scan all codeunits for bottlenecks")
    scan_parser.add_argument("-o", "--output", help="Save results to JSON file", metavar="FILE")
    scan_parser.add_argument("-l", "--limit", type=int, help="Limit number of bottlenecks displayed", metavar="N")

    optimize_parser = subparsers.add_parser("optimize", help="Generate optimization suggestions")
    optimize_parser.add_argument("filename", help="Codeunit filename (e.g., 1.cs)")

    # --- SETLOADFIELDS sub-command ---
    slf_parser = subparsers.add_parser(
        "setloadfields",
        help="Dedicated SETLOADFIELDS / SELECT-* audit: finds every read without SETLOADFIELDS, "
             "ranks tables by urgency (wide tables with many columns and FlowFields score highest).",
    )
    slf_parser.add_argument(
        "filename",
        nargs="?",
        default=None,
        help="Optional: limit audit to a single codeunit/table/page file. Omit to scan all files.",
    )
    slf_parser.add_argument(
        "--top",
        type=int,
        default=None,
        metavar="N",
        help="Show only the top N tables by urgency score (default: all).",
    )
    slf_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output raw JSON instead of human-readable report.",
    )
    slf_parser.add_argument(
        "-o", "--output",
        help="Save full findings to a JSON file.",
        metavar="FILE",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "list":
        return cmd_list()
    elif args.command == "analyze":
        return cmd_analyze(args.filename)
    elif args.command == "scan":
        return cmd_scan(output_file=args.output, limit=args.limit)
    elif args.command == "optimize":
        return cmd_optimize(args.filename)
    elif args.command == "setloadfields":
        return cmd_setloadfields(
            filename=args.filename,
            top=args.top,
            output_file=args.output,
            as_json=args.as_json,
        )


if __name__ == "__main__":
    sys.exit(main())
