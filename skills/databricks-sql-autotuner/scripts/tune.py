#!/usr/bin/env python3
"""Databricks SQL Tuner — benchmark and validate two SQL query variants.

Run with the venv Python created by env_setup.py:
    .venv_autotuner/bin/python scripts/tune.py [options]

Examples:
    # Explain the original query plan only
    .venv_autotuner/bin/python scripts/tune.py \\
        --profile my-profile --cluster-id 0123-456789-abcdefgh \\
        --original "SELECT * FROM sales WHERE year = 2024" \\
        --explain-only

    # Full benchmark (inline queries)
    .venv_autotuner/bin/python scripts/tune.py \\
        --profile my-profile --cluster-id 0123-456789-abcdefgh \\
        --original "SELECT ..." --optimized "SELECT ..." \\
        --catalog my_catalog --schema default --n-runs 3

    # Full benchmark (query files, @file syntax)
    .venv_autotuner/bin/python scripts/tune.py \\
        --profile my-profile --cluster-id 0123-456789-abcdefgh \\
        --original @original.sql --optimized @optimized.sql \\
        --n-runs 5
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_spark(profile: str, cluster_id: str):
    from databricks.connect import DatabricksSession
    return (
        DatabricksSession.builder
        .profile(profile)
        .clusterId(cluster_id)
        .getOrCreate()
    )


def set_context(spark, catalog: str | None, schema: str | None) -> None:
    if catalog:
        spark.sql(f"USE CATALOG {catalog}")
        print(f"[context] USE CATALOG {catalog}", file=sys.stderr)
    if schema:
        spark.sql(f"USE SCHEMA {schema}")
        print(f"[context] USE SCHEMA {schema}", file=sys.stderr)


def load_session_udfs(spark) -> None:
    """Load udf_setup.py from the current directory if it exists."""
    udf_file = Path("udf_setup.py")
    if not udf_file.exists():
        return
    print("[udfs] Loading udf_setup.py...", file=sys.stderr)
    spec = importlib.util.spec_from_file_location("udf_setup", udf_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "register_udfs"):
        mod.register_udfs(spark)
        print("[udfs] register_udfs() called.", file=sys.stderr)
    else:
        print("[udfs] Warning: udf_setup.py has no register_udfs(spark) function.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def load_query(arg: str) -> str:
    """Accept 'SELECT ...' inline or '@path/to/file.sql' for file-based queries."""
    if arg.startswith("@"):
        path = Path(arg[1:])
        if not path.exists():
            print(f"[error] Query file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8").strip()
    return arg.strip()


def explain_query(spark, query: str) -> str:
    rows = spark.sql(f"EXPLAIN EXTENDED {query}").collect()
    return "\n".join(str(r[0]) for r in rows)


# ---------------------------------------------------------------------------
# Table metadata & statistics
# ---------------------------------------------------------------------------

def _safe_sql(spark, sql: str) -> list:
    """Run a SQL statement, return rows, return [] on error (not all tables support all commands)."""
    try:
        return spark.sql(sql).collect()
    except Exception:
        return []


def collect_table_stats(spark, table_ref: str) -> dict:
    """
    Collect schema, partition columns, table-level stats, Delta physical detail,
    and per-column statistics for a single table reference.

    table_ref can be fully qualified (catalog.schema.table) or unqualified —
    the current USE CATALOG / USE SCHEMA context applies for unqualified names.
    """
    result: dict = {"table": table_ref}

    # --- Schema + partition columns + table stats ----------------------------
    # DESCRIBE EXTENDED returns rows with: col_name, data_type, comment
    # Special section rows have col_name like "# Partition Information", etc.
    desc_rows = _safe_sql(spark, f"DESCRIBE EXTENDED {table_ref}")
    columns = []
    partition_cols = []
    table_stats: dict = {}
    in_partition_section = False
    in_detail_section = False
    detail_buffer: dict = {}

    for row in desc_rows:
        col_name = (row["col_name"] or "").strip()
        data_type = (row["data_type"] or "").strip()
        comment = (row["comment"] or "").strip()

        # Section markers
        if col_name.startswith("# Partition Information"):
            in_partition_section = True
            in_detail_section = False
            continue
        if col_name.startswith("# Detailed Table Information"):
            in_partition_section = False
            in_detail_section = True
            continue
        if col_name.startswith("#"):
            in_partition_section = False
            # stay in detail section if already there
            continue

        if in_partition_section and col_name and data_type:
            partition_cols.append({"name": col_name, "type": data_type})
        elif in_detail_section and col_name:
            # Key-value pairs in detailed section
            detail_buffer[col_name] = data_type
        elif not in_partition_section and not in_detail_section and col_name and data_type:
            columns.append({"name": col_name, "type": data_type, "nullable": comment != "false"})

    # Extract table-level stats from detail section
    for key in ("Statistics", "Num Rows", "Total Size", "Raw Data Size"):
        if key in detail_buffer:
            table_stats[key] = detail_buffer[key]

    result["columns"] = columns
    result["partition_columns"] = partition_cols
    result["table_stats_from_describe"] = table_stats

    # --- Delta physical detail (numFiles, sizeInBytes, avgFileSize) ----------
    detail_rows = _safe_sql(spark, f"DESCRIBE DETAIL {table_ref}")
    if detail_rows:
        r = detail_rows[0].asDict()
        num_files = r.get("numFiles")
        size_bytes = r.get("sizeInBytes")
        result["delta_detail"] = {
            "format": r.get("format"),
            "numFiles": num_files,
            "sizeInBytes": size_bytes,
            "sizeMB": round(size_bytes / 1024 / 1024, 1) if size_bytes else None,
            "avgFileSizeMB": (
                round(size_bytes / num_files / 1024 / 1024, 2)
                if num_files and size_bytes and num_files > 0
                else None
            ),
            "location": r.get("location"),
            "partitionColumns": r.get("partitionColumns"),
        }
    else:
        result["delta_detail"] = None

    # --- Per-column statistics (populated only if ANALYZE has been run) ------
    col_stats: dict = {}
    for col in columns:
        stat_rows = _safe_sql(spark, f"DESCRIBE EXTENDED {table_ref} {col['name']}")
        stats = {}
        for row in stat_rows:
            k = (row["info_name"] or "").strip() if "info_name" in row.asDict() else ""
            v = (row["info_value"] or "").strip() if "info_value" in row.asDict() else ""
            if k and v:
                stats[k] = v
        interesting = {k: v for k, v in stats.items()
                       if k in ("min", "max", "num_nulls", "distinct_count", "avg_col_len", "max_col_len")}
        if interesting:
            col_stats[col["name"]] = interesting
    result["column_stats"] = col_stats  # empty dict if ANALYZE has not been run

    return result


def format_table_stats_report(stats_list: list[dict]) -> str:
    """Render collected table stats as a readable markdown report."""
    lines: list[str] = []
    for t in stats_list:
        name = t["table"]
        lines.append(f"## Table: `{name}`\n")

        # Delta physical summary
        dd = t.get("delta_detail")
        if dd:
            lines.append("### Physical (Delta)")
            lines.append(f"- Format: {dd.get('format', 'unknown')}")
            if dd.get("sizeMB") is not None:
                lines.append(f"- Size: **{dd['sizeMB']} MB** ({dd.get('sizeInBytes', '?')} bytes)")
            if dd.get("numFiles") is not None:
                lines.append(f"- Files: {dd['numFiles']}  |  avg file size: {dd.get('avgFileSizeMB', '?')} MB")
            if dd.get("partitionColumns"):
                lines.append(f"- Partition columns (physical): {dd['partitionColumns']}")
            lines.append("")

        # Table-level stats from DESCRIBE EXTENDED
        ts = t.get("table_stats_from_describe", {})
        if ts:
            lines.append("### Table statistics (from ANALYZE)")
            for k, v in ts.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        # Partition columns
        pc = t.get("partition_columns", [])
        if pc:
            lines.append(f"### Partition columns: {', '.join(c['name'] for c in pc)}")
            lines.append("")

        # Schema
        cols = t.get("columns", [])
        if cols:
            lines.append("### Schema")
            lines.append("| Column | Type | Nullable | min | max | nulls | distinct |")
            lines.append("|:-------|:-----|:---------|:----|:----|:------|:---------|")
            cs = t.get("column_stats", {})
            for c in cols:
                s = cs.get(c["name"], {})
                lines.append(
                    f"| {c['name']} | {c['type']} | {'Y' if c['nullable'] else 'N'} "
                    f"| {s.get('min', '—')} | {s.get('max', '—')} "
                    f"| {s.get('num_nulls', '—')} | {s.get('distinct_count', '—')} |"
                )
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------

def time_query(spark, query: str, n_runs: int, label: str) -> list[float]:
    """Run a query n_runs times and return wall-clock seconds per run."""
    times: list[float] = []
    for i in range(n_runs):
        start = time.perf_counter()
        spark.sql(query).collect()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"[bench] {label} run {i + 1}/{n_runs}: {elapsed:.2f}s", file=sys.stderr)
    return times


def compute_stats(times: list[float]) -> dict:
    n = len(times)
    mean = sum(times) / n
    variance = sum((t - mean) ** 2 for t in times) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(variance)
    return {
        "times_s": [round(t, 3) for t in times],
        "mean_s": round(mean, 3),
        "std_s": round(std, 3),
        "n": n,
    }


def is_significant(orig: dict, opt: dict) -> bool:
    """
    Returns True if the optimized query is faster with non-overlapping
    1-sigma confidence intervals:  opt.mean + opt.std < orig.mean - orig.std
    """
    return (opt["mean_s"] + opt["std_s"]) < (orig["mean_s"] - orig["std_s"])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_queries(spark, original: str, optimized: str) -> dict:
    """
    Store both queries as temp views and check:
    1. Row counts match
    2. Symmetric difference is empty (no rows in one that aren't in the other)
    """
    spark.sql(f"CREATE OR REPLACE TEMP VIEW _tuner_original AS {original}")
    spark.sql(f"CREATE OR REPLACE TEMP VIEW _tuner_optimized AS {optimized}")

    orig_count = spark.sql("SELECT COUNT(*) AS n FROM _tuner_original").collect()[0]["n"]
    opt_count = spark.sql("SELECT COUNT(*) AS n FROM _tuner_optimized").collect()[0]["n"]

    if orig_count != opt_count:
        return {
            "passed": False,
            "reason": f"Row count mismatch: original={orig_count}, optimized={opt_count}",
            "original_rows": orig_count,
            "optimized_rows": opt_count,
        }

    # Symmetric difference — up to 10 sample rows
    diff_df = spark.sql("""
        SELECT * FROM _tuner_original
        EXCEPT ALL
        SELECT * FROM _tuner_optimized
        UNION ALL
        SELECT * FROM _tuner_optimized
        EXCEPT ALL
        SELECT * FROM _tuner_original
    """).limit(10)

    diff_rows = diff_df.collect()
    if diff_rows:
        return {
            "passed": False,
            "reason": "Results differ (symmetric difference is non-empty)",
            "row_count": orig_count,
            "sample_diff": [r.asDict() for r in diff_rows[:5]],
        }

    return {"passed": True, "row_count": orig_count}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Benchmark and validate two Databricks SQL query variants.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--profile", required=True,
                   help="Databricks CLI profile name")
    p.add_argument("--cluster-id", required=True, dest="cluster_id",
                   help="Target cluster ID")
    p.add_argument("--original",
                   help="Original SQL string, or @path/to/file.sql "
                        "(required unless using --table-stats alone)")
    p.add_argument("--optimized",
                   help="Optimized SQL string, or @path/to/file.sql (omit with --explain-only)")
    p.add_argument("--catalog",
                   help="Run USE CATALOG before queries")
    p.add_argument("--schema",
                   help="Run USE SCHEMA before queries")
    p.add_argument("--n-runs", type=int, default=3, dest="n_runs",
                   help="Number of timed runs per variant (default: 3, min: 2)")
    p.add_argument("--explain-only", action="store_true", dest="explain_only",
                   help="Print EXPLAIN EXTENDED for the original query and exit")
    p.add_argument("--table-stats", nargs="+", dest="table_stats", metavar="TABLE",
                   help="Collect and print metadata + statistics for one or more tables. "
                        "Use before --explain-only to inform optimization decisions. "
                        "Tables can be fully qualified (catalog.schema.table) or unqualified.")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --table-stats is a standalone mode — no query required
    table_stats_only = args.table_stats and not getattr(args, "original", None)

    if not table_stats_only:
        if not args.explain_only and not args.optimized:
            parser.error("--optimized is required unless --explain-only or --table-stats is set")
        if args.n_runs < 2 and not args.explain_only:
            parser.error("--n-runs must be at least 2 for meaningful statistics")

    # Connect
    print(f"[connect] Connecting (profile={args.profile}, cluster={args.cluster_id})...",
          file=sys.stderr)
    spark = get_spark(args.profile, args.cluster_id)
    print(f"[connect] Spark {spark.version}", file=sys.stderr)

    set_context(spark, args.catalog, args.schema)
    load_session_udfs(spark)

    # --table-stats mode: collect and print metadata for requested tables
    if args.table_stats:
        print(f"\n[stats] Collecting metadata for: {', '.join(args.table_stats)}", file=sys.stderr)
        all_stats = []
        for tbl in args.table_stats:
            print(f"[stats] {tbl}...", file=sys.stderr)
            all_stats.append(collect_table_stats(spark, tbl))
        print(format_table_stats_report(all_stats))
        if table_stats_only:
            return

    original = load_query(args.original)
    optimized = load_query(args.optimized) if args.optimized else None

    # Explain-only mode
    if args.explain_only:
        print("\n[explain] EXPLAIN EXTENDED — original query\n", file=sys.stderr)
        plan = explain_query(spark, original)
        print(plan)
        return

    # Full mode: explain + validate + benchmark
    print("\n[explain] Running EXPLAIN EXTENDED on original...", file=sys.stderr)
    plan = explain_query(spark, original)

    print("\n[validate] Checking result equivalence...", file=sys.stderr)
    validation = validate_queries(spark, original, optimized)
    status = "PASS" if validation["passed"] else "FAIL"
    print(f"[validate] {status}", file=sys.stderr)

    print(f"\n[bench] Original ({args.n_runs} runs)...", file=sys.stderr)
    orig_times = time_query(spark, original, args.n_runs, "original")

    print(f"\n[bench] Optimized ({args.n_runs} runs)...", file=sys.stderr)
    opt_times = time_query(spark, optimized, args.n_runs, "optimized")

    orig_stats = compute_stats(orig_times)
    opt_stats = compute_stats(opt_times)
    speedup = orig_stats["mean_s"] / opt_stats["mean_s"] if opt_stats["mean_s"] > 0 else None
    significant = is_significant(orig_stats, opt_stats) if speedup and speedup > 1 else False

    result = {
        "explain_plan": plan,
        "validation": validation,
        "original": orig_stats,
        "optimized": opt_stats,
        "speedup": round(speedup, 3) if speedup else None,
        "statistically_significant": significant,
    }

    separator = "=" * 60
    print(f"\n{separator}", file=sys.stderr)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
