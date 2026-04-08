---
name: databricks-sql-autotuner
description: >
  Databricks SQL query optimizer: analyzes a slow SQL query, rewrites it for
  speed using SQL-level optimizations only, validates byte-for-byte result
  equivalence, and benchmarks both versions with statistical significance testing.
  Use this skill whenever the user wants to optimize, speed up, tune, or benchmark
  a SQL query on Databricks. Trigger on: "/databricks-sql-autotuner", "optimize
  this SQL", "make this query faster", "tune my Databricks query", "benchmark SQL
  on Databricks", "speed up this spark SQL", "SQL performance on Databricks",
  "EXPLAIN this query", "why is my query slow on Databricks", "SQL query
  optimization Databricks", or whenever a user pastes a SQL query and mentions
  performance, slowness, or runtime.
compatibility: Requires databricks CLI (authenticated) and Python 3.9+.
---

# Databricks SQL Autotuner

Analyze, rewrite, validate, and benchmark SQL queries against a live Databricks
cluster. The optimized query must produce **identical results** and show a
**statistically meaningful speedup** before it is accepted.

## Reference files

Read these before writing the optimized query:

| File | When to read |
|:-----|:------------|
| [`references/spark-sql-hints.md`](references/spark-sql-hints.md) | Any time you are considering a hint (`BROADCAST`, `MERGE`, `SHUFFLE_HASH`, `REBALANCE`, etc.) or dealing with UNION ALL scoping |
| [`references/spark-sql-perf-tuning.md`](references/spark-sql-perf-tuning.md) | For AQE behavior, partition tuning, statistics interpretation, and the full SQL-level optimization checklist |

---

## Phase 0 — Parse input

The user invokes with: `/databricks-sql-autotuner <query-or-path>`

- If the argument is a file path (ends in `.sql` or the path exists), read the file.
- Otherwise, treat the argument as an inline SQL string.
- If no argument was provided, ask the user to paste or provide the query now.

---

## Phase 1 — Environment discovery

### 1.1 Verify Databricks CLI is authenticated

```bash
databricks auth profiles
```

If this fails or returns no profiles, stop and ask the user to authenticate:
```bash
databricks auth login --profile <name>
```

### 1.2 Select profile

Present all available profiles with their workspace host URLs.
Ask the user which profile to use. Do not auto-select, even if only one exists.

### 1.3 Select cluster

```bash
databricks clusters list --profile <PROFILE> --output json
```

Filter to clusters with `state = RUNNING` or `state = TERMINATED` (can be started).
Present the list (cluster ID, name, state, DBR version).
Ask which cluster to target. Default to any running general-purpose cluster if one exists.

If the chosen cluster is terminated, start it:
```bash
databricks clusters start --cluster-id <CLUSTER_ID> --profile <PROFILE>
```

### 1.4 Get DBR version

```bash
databricks clusters get --cluster-id <CLUSTER_ID> --profile <PROFILE> \
  | python3 -c "import sys,json; v=json.load(sys.stdin)['spark_version']; print(v.split('-')[0])"
```

Record as `DBR_VERSION` (e.g., `17.3`). This determines which `databricks-connect` to install.

### 1.5 Catalog / schema context

Ask:
> **What catalog and schema should I use as the default context for this query?**
> (e.g., `my_catalog` / `default`, or `main` / `my_schema`)
> Press Enter to skip if the query uses fully qualified table names.

Record as `CATALOG` and `SCHEMA` (may be empty).

### 1.6 Benchmark runs

Ask:
> **How many benchmark runs per query variant? (default: 3)**

Record as `N_RUNS` (default `3`, minimum `2`).

### 1.7 Confirm

Present a summary and wait for confirmation:

| Parameter    | Value |
|:-------------|:------|
| Profile      |       |
| Cluster ID   |       |
| DBR version  |       |
| Catalog      |       |
| Schema       |       |
| N runs       |       |

---

## Phase 2 — Environment setup

Requires **uv**. Check it is available:
```bash
uv --version
```
If missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Run the setup script with the system Python (outside any venv):

```bash
python3 scripts/env_setup.py \
  --dbr-version <DBR_VERSION> \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID>
```

This uses `uv venv` to create `.venv_autotuner/`, installs
`databricks-connect==<DBR_VERSION>.*`, and verifies the connection with a
`SELECT 1` smoke test.

All subsequent commands use:
```bash
uv run --python .venv_autotuner/bin/python scripts/tune.py ...
# Windows: uv run --python .venv_autotuner\Scripts\python.exe scripts/tune.py ...
```

Record as `VENV_RUN = "uv run --python .venv_autotuner/bin/python"` (adjust path for Windows).

---

## Phase 3 — Query analysis

This phase has two parts: collect table metadata + statistics, then get the
execution plan. Together they give the full picture needed to make smart
optimization decisions.

### 3.1 Identify tables in the query

Read the query and extract every table reference (fully qualified or not).
For each table, you will collect metadata and stats in the next step.

### 3.2 Collect table metadata and statistics

```bash
<VENV_RUN> scripts/tune.py \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --table-stats <TABLE1> [<TABLE2> ...]
```

For each table this collects and prints:

| Section | Source | What it tells you |
|:--------|:-------|:------------------|
| **Schema** | `DESCRIBE table` | Column names, types, nullable |
| **Partition columns** | `DESCRIBE EXTENDED` | Which columns are partition keys — critical for predicate pushdown |
| **Table stats** | `DESCRIBE EXTENDED` | Row count, total size (if `ANALYZE TABLE` has been run) |
| **Delta detail** | `DESCRIBE DETAIL` | Physical file count, total bytes on disk, avg file size |
| **Column stats** | `DESCRIBE EXTENDED t col` | min, max, nullCount, distinctCount (per column, if computed) |

Use these facts to make optimization decisions:

| Fact | Decision |
|:-----|:---------|
| Delta detail `sizeInBytes` < 200 MB | Safe to BROADCAST this table in a join |
| Delta detail `numFiles` is very high | Consider Z-ordering or compaction (note as recommendation, not SQL change) |
| Avg file size < 32 MB | Small files problem — predicate pushdown likely hurting more than helping |
| No partition columns | All filters are post-scan; look for other pushdown opportunities |
| Filter column IS a partition column | Verify the WHERE clause actually uses it for pruning |
| Column `distinctCount` is low | High-skew risk in GROUP BY or JOIN on that column |
| Column `nullCount` is high | NULL-safe joins may inflate row counts unexpectedly |
| Row count from DESCRIBE ≠ actual COUNT(*) | Stats are stale — note this, but do not run ANALYZE (it can be slow) |

### 3.3 Get the execution plan

```bash
<VENV_RUN> scripts/tune.py \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original "<QUERY_OR_@FILE>" \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --explain-only
```

Cross-reference the plan with the table stats you just collected:

| Bottleneck signal | What to look for |
|:-----------------|:-----------------|
| BroadcastNestedLoopJoin | Missing join key or cartesian product — add explicit join condition |
| SortMergeJoin but table is < 200 MB | Add BROADCAST hint (check Delta detail size first) |
| Exchange (shuffle) | Heavy repartitioning — check GROUP BY / JOIN key cardinality |
| FileScan with no partition pruning | Add partition filter; verify partition columns from DESCRIBE EXTENDED |
| Filter after scan | Move filter earlier or rewrite WHERE to use partition columns |
| Repeated subquery | Extract to CTE or use window function |
| UNION ALL + aggregate | Check if ROLLUP or window can replace |
| UDF calls on large datasets | Consider replacing with built-in Spark SQL functions |
| Large row count with high-null join key | Add `IS NOT NULL` filter before join to reduce shuffle size |

---

## Phase 4 — SQL optimization

> **Output contract:** The only thing this skill produces is a rewritten SQL query.
> No Python code. No cluster config. No DataFrame API. No schema changes.
> A plain SQL string — same SELECT structure, same columns, same output — just faster.
> SQL hints (`/*+ BROADCAST(...) */`) and SQL comments are allowed.

Rewrite the query using **SQL-level rewrites only**.

### What is allowed

- Rewriting JOINs (inner ↔ left, reordering join tables for better plan)
- Adding / removing CTEs for de-duplication and readability
- Replacing correlated subqueries with joins or window functions
- Adding predicate filters earlier in the plan (push filters closer to the scan)
- Rewriting DISTINCT with GROUP BY where appropriate
- Replacing UDFs with equivalent built-in Spark SQL functions
- Splitting complex expressions to help predicate pushdown
- SQL optimizer hints: `/*+ BROADCAST(t) */`, `/*+ MERGE(t) */`, `/*+ SHUFFLE_HASH(t) */`
- SQL comments (`--` or `/* */`) explaining what the optimization does

### What is NOT allowed — never suggest these

- `spark.conf.set(...)` or any cluster/session configuration
- DataFrame / PySpark API code (`.filter()`, `.join()`, `.groupBy()`, etc.)
- DDL changes (`ALTER TABLE`, `OPTIMIZE`, `ZORDER`, `VACUUM`, `ANALYZE TABLE`)
- Any rewrite that changes columns, row count, or values in the output

If a non-SQL improvement (e.g., Z-ordering, cluster sizing) would help, mention it
separately under "Additional recommendations (outside scope)" in the final report —
but never include it in the optimized query itself.

### Hint restriction — CRITICAL for UNION ALL

Spark SQL does **not** allow `/*+ ... */` hints inside CTE branches that are
part of a `UNION ALL`. Place all optimizer hints on the **outermost SELECT only**:

```sql
-- ✅ CORRECT
SELECT /*+ BROADCAST(small_table) */ *
FROM big_table
JOIN small_table ON ...

-- ❌ WRONG — hint inside a UNION ALL branch causes a parse error
WITH branch AS (
  SELECT /*+ BROADCAST(t) */ * FROM t   -- this will fail
)
SELECT * FROM branch
UNION ALL
SELECT * FROM other
```

### UDF handling

If the query calls UDFs, check whether each is:
- A **persistent SQL function** (created with `CREATE FUNCTION` in the catalog) — these work as-is
- A **session UDF** that must be registered at runtime — create a `udf_setup.py` file (see below)

If session UDFs are needed, create `udf_setup.py` in the current directory:

```python
# udf_setup.py — loaded by tune.py automatically if it exists
from pyspark.sql.functions import udf as spark_udf
from pyspark.sql.types import StringType

def _my_udf(value):
    # your implementation
    return result

def register_udfs(spark):
    spark.udf.register("my_udf_name", spark_udf(_my_udf, StringType()))
```

`tune.py` checks for `udf_setup.py` in the current directory and calls
`register_udfs(spark)` automatically before running any queries.

---

## Phase 5 — Validate and benchmark

Once the optimized query is ready:

```bash
<VENV_RUN> scripts/tune.py \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original "<ORIGINAL_QUERY_OR_@FILE>" \
  --optimized "<OPTIMIZED_QUERY_OR_@FILE>" \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --n-runs <N_RUNS>
```

Use `@path/to/file.sql` syntax to pass queries from files instead of inline strings.

The script outputs JSON with:
- `validation.passed` — whether results are byte-for-byte identical
- `validation.row_count` — number of rows compared
- `original.mean`, `original.std` — timing stats
- `optimized.mean`, `optimized.std` — timing stats
- `speedup` — ratio of original mean to optimized mean
- `statistically_significant` — true if optimized CI is entirely below original CI

### Interpreting results

A speedup is **real** only when:
1. `validation.passed = true` (identical results)
2. `speedup > 1.0` (optimized is faster on average)
3. `statistically_significant = true` (confidence intervals don't overlap)

If validation fails: the optimized query changed the output — fix it before benchmarking further.

If speedup is not statistically significant: run more iterations (`--n-runs 5` or `--n-runs 7`),
or try a more aggressive optimization.

---

## Phase 6 — Report

Present a summary:

```
## SQL Tuning Report

### Query plan bottlenecks (original)
<key findings from EXPLAIN>

### Optimizations applied
1. <change 1 — what + why>
2. <change 2 — what + why>
...

### Original SQL
<original query>

### Optimized SQL
<optimized query>

### Benchmark results
| Variant   | Mean (s) | Std (s) | Runs |
|:----------|:---------|:--------|:-----|
| Original  | x.xx     | x.xx    | N    |
| Optimized | x.xx     | x.xx    | N    |

Speedup: X.Xx  |  Statistically significant: yes/no
Validation: PASS — N rows, identical results

### Conclusion
<one paragraph: what changed, why it helped, any caveats>
```

If the speedup is not statistically significant, explain why and suggest next steps
(more runs, a different optimization angle, or accept that the bottleneck is elsewhere).

---

## Troubleshooting

| Error | Fix |
|:------|:----|
| `Cannot configure default credentials` | Re-authenticate: `databricks auth login --profile <PROFILE>` |
| `Cluster not found` | Verify cluster ID: `databricks clusters list --profile <PROFILE>` |
| Version mismatch | Ensure `DBR_VERSION` from `clusters get` matches installed `databricks-connect` |
| `.venv_autotuner` import errors | Delete the venv and re-run `env_setup.py` |
| Validation diff on floats | May be floating-point non-determinism — check with `ROUND()` or cast to DECIMAL |
| Hint parse error in UNION ALL | Move hint to outermost SELECT (see Phase 4 restriction) |
| Session UDF not found | Create `udf_setup.py` with a `register_udfs(spark)` function |
