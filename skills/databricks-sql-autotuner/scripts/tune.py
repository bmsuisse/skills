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
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pyspark.sql.types import (
    ArrayType, BooleanType, ByteType, DecimalType, DoubleType, FloatType,
    IntegerType, LongType, MapType, ShortType, StructType,
)
from pathlib import Path


def _progress(done: int, total: int, label: str, elapsed: float | None = None) -> None:
    """Draw or update a single-line progress bar on stderr."""
    width = 30
    filled = int(width * done / total) if total else 0
    bar = "█" * filled + "░" * (width - filled)
    suffix = f" {elapsed:.1f}s" if elapsed is not None else ""
    end = "\n" if done == total else "\r"
    print(f"  [{bar}] {done}/{total} {label}{suffix}\033[K", end=end, file=sys.stderr, flush=True)


def get_spark(profile: str, cluster_id: str):
    from databricks.connect import DatabricksSession
    return DatabricksSession.builder.profile(profile).clusterId(cluster_id).getOrCreate()


def set_context(spark, catalog: str | None, schema: str | None) -> None:
    if catalog:
        spark.sql(f"USE CATALOG {catalog}")
        print(f"[context] USE CATALOG {catalog}", file=sys.stderr)
    if schema:
        spark.sql(f"USE SCHEMA {schema}")
        print(f"[context] USE SCHEMA {schema}", file=sys.stderr)


def load_session_udfs(spark) -> None:
    udf_file = Path("udf_setup.py")
    if not udf_file.exists():
        return
    print("[udfs] Loading udf_setup.py...", file=sys.stderr)
    spec = importlib.util.spec_from_file_location("udf_setup", udf_file)
    if spec is None or spec.loader is None:
        print("[udfs] Warning: could not load spec for udf_setup.py", file=sys.stderr)
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if hasattr(mod, "register_udfs"):
        mod.register_udfs(spark)
        print("[udfs] register_udfs() called.", file=sys.stderr)
    else:
        print("[udfs] Warning: udf_setup.py has no register_udfs(spark) function.", file=sys.stderr)


def load_query(arg: str) -> str:
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


def _safe_sql(spark, sql: str) -> list:
    try:
        return spark.sql(sql).collect()
    except Exception as e:
        print(f"[warn] SQL skipped ({e})", file=sys.stderr)
        return []


def collect_table_stats(spark, table_ref: str) -> dict:
    result: dict = {"table": table_ref}

    desc_rows = _safe_sql(spark, f"DESCRIBE EXTENDED {table_ref}")
    columns, partition_cols, detail_buffer = [], [], {}
    in_partition = in_detail = False

    for row in desc_rows:
        col_name = (row["col_name"] or "").strip()
        data_type = (row["data_type"] or "").strip()
        comment = (row["comment"] or "").strip()

        if col_name.startswith("# Partition Information"):
            in_partition, in_detail = True, False
            continue
        if col_name.startswith("# Detailed Table Information"):
            in_partition, in_detail = False, True
            continue
        if col_name.startswith("#"):
            in_partition = False
            continue

        if in_partition and col_name and data_type:
            partition_cols.append({"name": col_name, "type": data_type})
        elif in_detail and col_name:
            detail_buffer[col_name] = data_type
        elif not in_partition and not in_detail and col_name and data_type:
            columns.append({"name": col_name, "type": data_type, "nullable": comment != "false"})

    result["columns"] = columns
    result["partition_columns"] = partition_cols
    result["table_stats_from_describe"] = {
        k: detail_buffer[k]
        for k in ("Statistics", "Num Rows", "Total Size", "Raw Data Size")
        if k in detail_buffer
    }

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
                if num_files and size_bytes
                else None
            ),
            "location": r.get("location"),
            "partitionColumns": r.get("partitionColumns"),
        }
    else:
        result["delta_detail"] = None

    col_stats: dict = {}
    stat_keys = ("min", "max", "num_nulls", "distinct_count", "avg_col_len", "max_col_len")
    for col in columns:
        rows = _safe_sql(spark, f"DESCRIBE EXTENDED {table_ref} {col['name']}")
        stats = {
            row["info_name"].strip(): row["info_value"].strip()
            for row in rows
            if "info_name" in row.asDict() and row["info_name"] and row["info_value"]
        }
        interesting = {k: v for k, v in stats.items() if k in stat_keys}
        if interesting:
            col_stats[col["name"]] = interesting
    result["column_stats"] = col_stats

    return result


def format_table_stats_report(stats_list: list[dict]) -> str:
    lines: list[str] = []
    for t in stats_list:
        lines.append(f"## Table: `{t['table']}`\n")

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

        ts = t.get("table_stats_from_describe", {})
        if ts:
            lines.append("### Table statistics (from ANALYZE)")
            for k, v in ts.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        pc = t.get("partition_columns", [])
        if pc:
            lines.append(f"### Partition columns: {', '.join(c['name'] for c in pc)}")
            lines.append("")

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


def time_query(spark, query: str, n_runs: int, label: str, timing_count: bool = False) -> list[float]:
    exec_sql = f"SELECT COUNT(*) AS n FROM ({query})" if timing_count else query
    times: list[float] = []
    _progress(0, n_runs, label)
    for i in range(n_runs):
        start = time.perf_counter()
        spark.sql(exec_sql).collect()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        _progress(i + 1, n_runs, label, elapsed)
    return times


def compute_stats(times: list[float]) -> dict:
    n = len(times)
    mean = sum(times) / n
    std = math.sqrt(sum((t - mean) ** 2 for t in times) / (n - 1)) if n > 1 else 0.0
    return {"times_s": [round(t, 3) for t in times], "mean_s": round(mean, 3), "std_s": round(std, 3), "n": n}


def is_significant(orig: dict, opt: dict) -> bool:
    # Non-overlapping 1-sigma CIs: opt.mean + opt.std < orig.mean - orig.std
    return (opt["mean_s"] + opt["std_s"]) < (orig["mean_s"] - orig["std_s"])


def _normalize_expr(expr: str, dtype) -> str:
    """Recursively build a deterministic SQL expression for non-deterministic types.

    - ArrayType  → array_sort(transform(expr, x -> normalize(x)))
    - MapType    → cast(expr AS STRING)  (no sort available for maps)
    - StructType → struct(normalize(field1) AS field1, ...)
    - other      → expr unchanged
    """
    if isinstance(dtype, ArrayType):
        inner = _normalize_expr("x", dtype.elementType)
        if inner == "x":
            return f"array_sort({expr})"
        return f"array_sort(transform({expr}, x -> {inner}))"
    elif isinstance(dtype, MapType):
        return f"cast({expr} AS STRING)"
    elif isinstance(dtype, StructType):
        fields = ", ".join(
            f"{_normalize_expr(f'{expr}.`{f.name}`', f.dataType)} AS `{f.name}`"
            for f in dtype.fields
        )
        return f"struct({fields})"
    return expr


def _normalized_select(schema) -> str:
    """SELECT clause that normalizes array/map/struct columns for deterministic EXCEPT ALL comparison."""
    parts = []
    for field in schema.fields:
        col = f"`{field.name}`"
        normalized = _normalize_expr(col, field.dataType)
        parts.append(f"{normalized} AS {col}" if normalized != col else col)
    return ", ".join(parts)


def validate_queries(spark, original: str, optimized: str) -> dict:
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

    schema = spark.sql("SELECT * FROM _tuner_original LIMIT 0").schema
    sel = _normalized_select(schema)
    diff_rows = spark.sql(f"""
        SELECT {sel} FROM _tuner_original EXCEPT ALL SELECT {sel} FROM _tuner_optimized
        UNION ALL
        SELECT {sel} FROM _tuner_optimized EXCEPT ALL SELECT {sel} FROM _tuner_original
    """).limit(10).collect()

    if diff_rows:
        return {
            "passed": False,
            "reason": "Results differ (symmetric difference is non-empty)",
            "row_count": orig_count,
            "sample_diff": [r.asDict() for r in diff_rows[:5]],
        }

    return {"passed": True, "row_count": orig_count}


def validate_queries_global_temp(spark, original: str, optimized: str) -> dict:
    """Validate via global temp tables — results are cached on the cluster, nothing collected to driver."""
    spark.sql(f"CREATE OR REPLACE GLOBAL TEMP VIEW _tuner_original AS {original}")
    spark.sql(f"CREATE OR REPLACE GLOBAL TEMP VIEW _tuner_optimized AS {optimized}")
    spark.sql("CACHE TABLE global_temp._tuner_original")
    spark.sql("CACHE TABLE global_temp._tuner_optimized")

    orig_count = spark.sql("SELECT COUNT(*) AS n FROM global_temp._tuner_original").collect()[0]["n"]
    opt_count = spark.sql("SELECT COUNT(*) AS n FROM global_temp._tuner_optimized").collect()[0]["n"]

    if orig_count != opt_count:
        return {
            "passed": False,
            "reason": f"Row count mismatch: original={orig_count}, optimized={opt_count}",
            "original_rows": orig_count,
            "optimized_rows": opt_count,
        }

    schema = spark.sql("SELECT * FROM global_temp._tuner_original LIMIT 0").schema
    sel = _normalized_select(schema)
    diff_rows = spark.sql(f"""
        SELECT {sel} FROM global_temp._tuner_original EXCEPT ALL SELECT {sel} FROM global_temp._tuner_optimized
        UNION ALL
        SELECT {sel} FROM global_temp._tuner_optimized EXCEPT ALL SELECT {sel} FROM global_temp._tuner_original
    """).limit(10).collect()

    if diff_rows:
        return {
            "passed": False,
            "reason": "Results differ (symmetric difference is non-empty)",
            "row_count": orig_count,
            "sample_diff": [r.asDict() for r in diff_rows[:5]],
        }

    return {"passed": True, "row_count": orig_count}


def validate_queries_checksum(spark, original: str, optimized: str) -> dict:
    """Validate by comparing aggregate checksums on numeric and boolean columns only.

    Suitable for large tables where full EXCEPT ALL is too expensive.
    Checks row count, then SUM + COUNT of every numeric/boolean column.
    """
    _NUMERIC = (ByteType, ShortType, IntegerType, LongType, FloatType, DoubleType, DecimalType)

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
            "strategy": "checksum",
        }

    schema = spark.sql("SELECT * FROM _tuner_original LIMIT 0").schema
    agg_exprs: list[str] = []
    checksum_cols: list[str] = []

    for field in schema.fields:
        col = f"`{field.name}`"
        safe = re.sub(r"[^a-zA-Z0-9]", "_", field.name)
        if isinstance(field.dataType, _NUMERIC):
            agg_exprs += [f"SUM({col}) AS sum_{safe}", f"COUNT({col}) AS cnt_{safe}"]
            checksum_cols.append(field.name)
        elif isinstance(field.dataType, BooleanType):
            agg_exprs += [f"SUM(CAST({col} AS BIGINT)) AS sum_{safe}", f"COUNT({col}) AS cnt_{safe}"]
            checksum_cols.append(field.name)

    if not checksum_cols:
        return {
            "passed": True,
            "row_count": orig_count,
            "strategy": "checksum",
            "note": "No numeric/boolean columns — row count only",
        }

    agg_sql = ", ".join(agg_exprs)
    orig_agg = spark.sql(f"SELECT {agg_sql} FROM _tuner_original").collect()[0].asDict()
    opt_agg = spark.sql(f"SELECT {agg_sql} FROM _tuner_optimized").collect()[0].asDict()

    mismatches = {
        k: {"original": orig_agg[k], "optimized": opt_agg[k]}
        for k in orig_agg
        if orig_agg[k] != opt_agg[k]
    }

    if mismatches:
        return {
            "passed": False,
            "reason": "Checksum mismatch on numeric/boolean columns",
            "row_count": orig_count,
            "mismatches": mismatches,
            "strategy": "checksum",
            "columns_checked": checksum_cols,
        }

    return {"passed": True, "row_count": orig_count, "strategy": "checksum", "columns_checked": checksum_cols}


def validate_queries_row_hash(spark, original: str, optimized: str) -> dict:
    """Validate using a commutative row hash for huge tables.

    Computes SUM(xxhash64(col1, col2, ...)) across all rows — a single aggregation
    pass per query, order-independent, and handles all column types.
    Catches any value-level difference without collecting rows to the driver.
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
            "strategy": "row_hash",
        }

    schema = spark.sql("SELECT * FROM _tuner_original LIMIT 0").schema
    col_list = ", ".join(f"`{f.name}`" for f in schema.fields)
    hash_sql = f"SELECT SUM(xxhash64({col_list})) AS row_hash FROM"

    orig_hash = spark.sql(f"{hash_sql} _tuner_original").collect()[0]["row_hash"]
    opt_hash = spark.sql(f"{hash_sql} _tuner_optimized").collect()[0]["row_hash"]

    if orig_hash != opt_hash:
        return {
            "passed": False,
            "reason": f"Row hash mismatch: original={orig_hash}, optimized={opt_hash}",
            "row_count": orig_count,
            "strategy": "row_hash",
        }

    return {"passed": True, "row_count": orig_count, "strategy": "row_hash"}


def time_query_global_temp(spark, query: str, n_runs: int, label: str) -> list[float]:
    """Time query by materializing into a cached global temp table — avoids driver collection."""
    name = f"_tuner_{label}"
    times: list[float] = []
    _progress(0, n_runs, label)
    for i in range(n_runs):
        _safe_sql(spark, f"UNCACHE TABLE IF EXISTS global_temp.{name}")
        start = time.perf_counter()
        spark.sql(f"CREATE OR REPLACE GLOBAL TEMP VIEW {name} AS {query}")
        spark.sql(f"CACHE TABLE global_temp.{name}")
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        _progress(i + 1, n_runs, label, elapsed)
    _safe_sql(spark, f"UNCACHE TABLE IF EXISTS global_temp.{name}")
    return times


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Benchmark and validate two Databricks SQL query variants.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--profile", required=True)
    p.add_argument("--cluster-id", required=True, dest="cluster_id")
    p.add_argument("--original", help="SQL string or @path/to/file.sql")
    p.add_argument("--optimized", help="SQL string or @path/to/file.sql")
    p.add_argument("--catalog")
    p.add_argument("--schema")
    p.add_argument("--n-runs", type=int, default=3, dest="n_runs")
    p.add_argument("--explain-only", action="store_true", dest="explain_only")
    p.add_argument("--timing-count", action="store_true", dest="timing_count",
                   help="Wrap timing runs in COUNT(*) to avoid collecting large result sets to the driver")
    p.add_argument("--global-temp", action="store_true", dest="global_temp",
                   help="Materialize results into cached global temp tables on the cluster instead of "
                        "collecting to the driver (use when result sets are too large even for COUNT(*))")
    p.add_argument(
        "--compare-strategy",
        dest="compare_strategy",
        choices=["full", "extend", "checksum", "row_hash"],
        default=None,
        help=(
            "Validation strategy: "
            "'full' = EXCEPT ALL symmetric diff (default, precise, small-medium tables); "
            "'extend' = EXCEPT ALL via on-cluster global temp tables (medium tables); "
            "'checksum' = SUM+COUNT per numeric/boolean column (large tables, no row collection); "
            "'row_hash' = SUM(xxhash64(all_cols)) single-pass (huge tables, fastest)."
        ),
    )
    p.add_argument("--table-stats", nargs="+", dest="table_stats", metavar="TABLE",
                   help="Collect metadata + stats for tables (fully qualified or unqualified)")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    table_stats_only = args.table_stats and not args.original

    if not table_stats_only:
        if not args.explain_only and not args.optimized:
            parser.error("--optimized is required unless --explain-only or --table-stats is set")
        if args.n_runs < 1 and not args.explain_only:
            parser.error("--n-runs must be at least 1")
        if args.n_runs == 1 and not args.explain_only:
            print("[warn] --n-runs 1: single run — for meaningful statistics use 2 or more", file=sys.stderr)

    print(f"[connect] Connecting (profile={args.profile}, cluster={args.cluster_id})...", file=sys.stderr)
    spark = get_spark(args.profile, args.cluster_id)
    print(f"[connect] Spark {spark.version}", file=sys.stderr)

    set_context(spark, args.catalog, args.schema)
    load_session_udfs(spark)

    if args.table_stats:
        tables = args.table_stats
        print(f"\n[stats] Collecting metadata for {len(tables)} table(s) in parallel: {', '.join(tables)}", file=sys.stderr)
        raw: dict[str, dict] = {}
        done = 0
        _progress(0, len(tables), "collecting table stats")
        with ThreadPoolExecutor(max_workers=min(len(tables), 8)) as pool:
            futures = {pool.submit(collect_table_stats, spark, tbl): tbl for tbl in tables}
            for fut in as_completed(futures):
                tbl = futures[fut]
                try:
                    raw[tbl] = fut.result()
                except Exception as exc:
                    print(f"\n[stats] error for {tbl}: {exc}", file=sys.stderr)
                    raw[tbl] = {"table": tbl, "error": str(exc)}
                done += 1
                _progress(done, len(tables), "collecting table stats")
        # preserve input order
        print(format_table_stats_report([raw[t] for t in tables if t in raw]))
        if table_stats_only:
            return

    original = load_query(args.original)
    optimized = load_query(args.optimized) if args.optimized else None

    if args.explain_only:
        print("\n[explain] EXPLAIN EXTENDED — original query\n", file=sys.stderr)
        print(explain_query(spark, original))
        return

    assert optimized is not None, "--optimized required (enforced by parser.error above)"

    print("\n[explain] Running EXPLAIN EXTENDED on original...", file=sys.stderr)
    plan = explain_query(spark, original)

    # Resolve compare strategy: explicit flag > --global-temp backward-compat > default full
    compare_strategy = args.compare_strategy
    if compare_strategy is None:
        compare_strategy = "extend" if args.global_temp else "full"

    print(f"\n[validate] Checking result equivalence (strategy={compare_strategy})...", file=sys.stderr)
    try:
        if compare_strategy == "extend":
            validation = validate_queries_global_temp(spark, original, optimized)
        elif compare_strategy == "checksum":
            validation = validate_queries_checksum(spark, original, optimized)
        elif compare_strategy == "row_hash":
            validation = validate_queries_row_hash(spark, original, optimized)
        else:
            validation = validate_queries(spark, original, optimized)
        print(f"[validate] {'PASS' if validation['passed'] else 'FAIL'}", file=sys.stderr)

        if args.global_temp:
            print("[bench] Using global temp tables for timing and validation (--global-temp)", file=sys.stderr)
        elif args.timing_count:
            print("[bench] Using COUNT(*) wrapper for timing (--timing-count)", file=sys.stderr)

        print(f"\n[bench] Original ({args.n_runs} runs)...", file=sys.stderr)
        if args.global_temp:
            orig_times = time_query_global_temp(spark, original, args.n_runs, "original")
        else:
            orig_times = time_query(spark, original, args.n_runs, "original", args.timing_count)

        print(f"\n[bench] Optimized ({args.n_runs} runs)...", file=sys.stderr)
        if args.global_temp:
            opt_times = time_query_global_temp(spark, optimized, args.n_runs, "optimized")
        else:
            opt_times = time_query(spark, optimized, args.n_runs, "optimized", args.timing_count)

        orig_stats = compute_stats(orig_times)
        opt_stats = compute_stats(opt_times)
        speedup = orig_stats["mean_s"] / opt_stats["mean_s"] if opt_stats["mean_s"] > 0 else None

        print(f"\n{'=' * 60}", file=sys.stderr)
        print(json.dumps({
            "explain_plan": plan,
            "validation": validation,
            "original": orig_stats,
            "optimized": opt_stats,
            "speedup": round(speedup, 3) if speedup else None,
            "statistically_significant": is_significant(orig_stats, opt_stats) if speedup and speedup > 1 else False,
        }, indent=2))
    finally:
        if args.global_temp:
            print("[cleanup] Dropping global temp tables...", file=sys.stderr)
            for name in ("_tuner_original", "_tuner_optimized"):
                _safe_sql(spark, f"UNCACHE TABLE IF EXISTS global_temp.{name}")
                _safe_sql(spark, f"DROP VIEW IF EXISTS global_temp.{name}")


if __name__ == "__main__":
    main()
