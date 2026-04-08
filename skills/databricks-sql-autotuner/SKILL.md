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

## Examples

```
# Minimal — paste an inline query, discover everything automatically
/databricks-sql-autotuner "SELECT o.order_id, SUM(l.amount) FROM orders o JOIN lines l ON o.id = l.order_id GROUP BY o.order_id"

# From a file, cluster by ID
/databricks-sql-autotuner --cluster-id 0408-195905-abc --profile premium @queries/slow_report.sql

# From a file, cluster by name
/databricks-sql-autotuner --cluster-name my-cluster --profile premium @queries/slow_report.sql

# Optimize for speed, 5 benchmark runs
/databricks-sql-autotuner --cluster-id 0408-195905-abc --goals speed --runs 5 @queries/slow_report.sql

# Optimize for speed first, then simplify
/databricks-sql-autotuner --cluster-id 0408-195905-abc --goals speed,simplicity @queries/slow_report.sql

# Override catalog and schema
/databricks-sql-autotuner --cluster-id 0408-195905-abc --catalog sales --schema prod @queries/slow_report.sql
```

---

## Reference files

Read these before writing the optimized query:

| File | When to read |
|:-----|:------------|
| [`references/spark-sql-hints.md`](references/spark-sql-hints.md) | Any time you are considering a hint (`BROADCAST`, `MERGE`, `SHUFFLE_HASH`, `REBALANCE`, etc.) or dealing with UNION ALL scoping |
| [`references/spark-sql-perf-tuning.md`](references/spark-sql-perf-tuning.md) | For AQE behavior, partition tuning, statistics interpretation, and the full SQL-level optimization checklist |

---

## Phase 0 — Parse input

The user invokes with:

```
/databricks-sql-autotuner [options] <query-or-path>
```

Supported options (all optional — skip any discovery step where the value is provided):

| Option | Example | Effect |
|:-------|:--------|:-------|
| `--cluster-id <id>` | `--cluster-id 0408-195905-abc` | Skip cluster listing; use this cluster ID directly |
| `--cluster-name <name>` | `--cluster-name my-cluster` | Skip cluster listing; find cluster by name |
| `--profile <name>` | `--profile premium` | Skip profile selection; use this profile |
| `--catalog <name>` | `--catalog my_catalog` | Skip catalog discovery; use this value |
| `--schema <name>` | `--schema my_schema` | Skip schema discovery; use this value |
| `--runs <n>` | `--runs 5` | Override default benchmark run count (default: 3) |
| `--goals <list>` | `--goals speed` | Comma-separated goals: `speed`, `simplicity`, or `speed,simplicity` |

Record as `GOALS` (default: `speed`). Accepted values:

| Value | Meaning |
|:------|:--------|
| `speed` | Minimize execution time |
| `simplicity` | Minimize complexity score (lines, nesting, subqueries) |
| `speed,simplicity` | Optimize speed first; once accepted, simplify while staying within 10% of best time |

Parse these from the invocation arguments before starting Phase 1. For any option
not supplied, run the normal discovery step.

| `--query <sql-or-path>` | `--query @slow.sql` | SQL string or `@path/to/file.sql`; if omitted, ask the user |
| `--optimized <path>` | `--optimized out.sql` | Write optimized query to a separate file instead of editing the original in place |

The `--query` value:
- `@path/to/file.sql` → read the file
- Any other string → treat as inline SQL
- Omitted → ask the user to paste or provide the query

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

If `--profile` was provided, skip this step.

Otherwise present all available profiles with their workspace host URLs.
Auto-select if only one exists; otherwise ask.

### 1.3 Select cluster

If `--cluster-id` was provided, use that ID directly and skip the listing.

If `--cluster-name` was provided, resolve it to an ID:

```bash
databricks clusters list --profile <PROFILE> --output json \
  | python3 -c "
import sys, json
clusters = json.load(sys.stdin)
name = '<CLUSTER_NAME>'
match = [c for c in clusters if c.get('cluster_name') == name]
if not match:
    print('ERROR: no cluster named', name, file=sys.stderr); sys.exit(1)
print(match[0]['cluster_id'])
"
```

If neither was provided, list all clusters:

```bash
databricks clusters list --profile <PROFILE> --output json
```

Filter to clusters with `state = RUNNING` or `state = TERMINATED` (can be started).
Present the list (cluster ID, name, state, DBR version).
Auto-select any running general-purpose cluster if one exists; otherwise ask.

If the chosen cluster is terminated, start it:
```bash
databricks clusters start <CLUSTER_ID> --profile <PROFILE>
```

### 1.4 Get DBR version

```bash
databricks clusters get <CLUSTER_ID> --profile <PROFILE> --output json \
  | python3 -c "import sys,json; v=json.load(sys.stdin)['spark_version']; print(v.split('-')[0])"
```

Record as `DBR_VERSION` (e.g., `17.3`). This determines which `databricks-connect` to install.

### 1.5 Catalog / schema context

Run to discover the current defaults:

```bash
databricks clusters get <CLUSTER_ID> --profile <PROFILE> --output json \
  | python3 -c "import sys,json; c=json.load(sys.stdin); \
    cfg=c.get('spark_conf',{}); \
    print('catalog:', cfg.get('spark.databricks.sql.initial.catalog.name','hive_metastore')); \
    print('schema:', cfg.get('spark.databricks.sql.initial.catalog.namespace','default'))"
```

Use whatever the cluster reports as `CATALOG` and `SCHEMA`. Only ask the user to
override if the query explicitly references a different catalog/schema or if the
command returns nothing useful.

### 1.6 Benchmark runs

If `--runs` was provided, skip this step and use that value.

Otherwise ask:
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

### 2.0 Resolve the skill directory

The scripts live inside the skill, not the project. Locate them first:

```bash
SKILL_DIR=$(find ~/.claude/skills/databricks-sql-autotuner \
                  "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/skills/databricks-sql-autotuner" \
             -maxdepth 0 -type d 2>/dev/null | head -1)
echo "SKILL_DIR=$SKILL_DIR"
```

If neither path exists, check where Claude Code installed the skill:
```bash
find ~ -path "*/.claude/skills/databricks-sql-autotuner" -maxdepth 6 -type d 2>/dev/null | head -1
```

Record as `SKILL_DIR`. All script paths below use `$SKILL_DIR/scripts/`.

### 2.1 Check uv

```bash
uv --version
```
If missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2.2 Run setup

```bash
python3 "$SKILL_DIR/scripts/env_setup.py" \
  --dbr-version <DBR_VERSION> \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID>
```

This uses `uv venv` to create `.venv_autotuner/`, installs
`databricks-connect==<DBR_VERSION>.*`, and verifies the connection with a
`SELECT 1` smoke test.

All subsequent commands invoke the venv Python directly:

```bash
VENV_PYTHON=".venv_autotuner/bin/python"          # macOS / Linux
# Windows: VENV_PYTHON=".venv_autotuner\Scripts\python.exe"
TUNE="$VENV_PYTHON $SKILL_DIR/scripts/tune.py"
```

Use `$TUNE` for every `tune.py` invocation from here on.

---

## Phase 2b — Branch & baseline

Every tuning session gets its own branch and a results log. This keeps the work
isolated, makes it easy to compare iterations, and produces a clean git history
that shows exactly what was tried and kept.

### 2b.1 Generate a run ID

Use a short slug derived from the query's purpose — e.g. `sales-summary`, `user-funnel-join`.

```bash
RUN_ID="<query-slug>"           # e.g. sales-summary
RESULTS_FILE="sqltune-${RUN_ID}.tsv"
LOG_FILE="sqltune-${RUN_ID}.log"
```

### 2b.2 Create a branch

```bash
git checkout -b sql-tune/${RUN_ID}
```

### 2b.3 Establish the working file

Determine `QUERY_FILE` (the file that will be edited each iteration) and
`ORIGINAL_FILE` (the baseline passed to `--original` in tune.py):

| Scenario | ORIGINAL_FILE | QUERY_FILE |
|:---------|:-------------|:-----------|
| `--query @file.sql` (default) | `file.sql` | `file.sql` — edit in place |
| `--query @file.sql --optimized out.sql` | `file.sql` | `out.sql` — write here, original stays untouched |
| `--query "inline SQL"` | `query.sql` (write it, commit) | `query.sql` — edit in place |
| `--query "inline SQL" --optimized out.sql` | `query.sql` | `out.sql` |

When `--optimized` is given, copy the original into that file first:
```bash
cp $ORIGINAL_FILE $QUERY_FILE
git add $QUERY_FILE
```

When editing in place (no `--optimized`), `ORIGINAL_FILE == QUERY_FILE` and git tracks the evolution naturally.

### 2b.4 Initialize the results log

```bash
echo "${RESULTS_FILE}" >> .git/info/exclude
echo "${LOG_FILE}"     >> .git/info/exclude
```

Create `$RESULTS_FILE`:

```
attempt	commit	mean_s	speedup	status	description
0	<sha>	<baseline_mean>	1.0	baseline	original query
```

### 2b.5 Run the baseline

```bash
$TUNE \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original @$QUERY_FILE \
  --optimized @$QUERY_FILE \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --n-runs <N_RUNS> > $LOG_FILE 2>&1
```

Extract `original.mean_s` and record as attempt `0`.

> Baseline: **mean = X.XXs**. Branch: `sql-tune/<run-id>`. Starting analysis.

---

## Phase 3 — Query analysis

Start with the execution plan — it tells you what the optimizer actually decided.
Collect table stats only when the plan raises a question that size or schema data
would answer (e.g. "is this table small enough to broadcast?").

### 3.1 Get the execution plan

```bash
$TUNE \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original "<QUERY_OR_@FILE>" \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --explain-only
```

Read the plan and identify bottlenecks:

| Bottleneck signal | What to look for |
|:-----------------|:-----------------|
| BroadcastNestedLoopJoin | Missing join key or cartesian product — add explicit join condition |
| SortMergeJoin | May be improvable with BROADCAST if the smaller side is small enough — check table size |
| Exchange (shuffle) | Heavy repartitioning — check GROUP BY / JOIN key cardinality |
| FileScan with no PartitionFilters | Filter may not be using partition columns — worth checking schema |
| Filter after scan (not pushed) | Move filter earlier or rewrite WHERE to use partition columns |
| Repeated subquery | Extract to CTE or use window function |
| UNION ALL + aggregate | Check if ROLLUP or window can replace |
| UDF calls on large datasets | Consider replacing with built-in Spark SQL functions |
| Large row count with high-null join key | Add `IS NOT NULL` filter before join to reduce shuffle size |
| SubqueryAlias / deep nested plan where a FileScan is expected | Join target is a view — read the view definition (step 3.2a) |
| Skewed Exchange — one partition vastly larger than others | GROUP BY key has low or highly uneven cardinality — consider SQL salting (see Phase 4) |
| `IN (subquery)` | Often generates a worse plan than `EXISTS` or a semi-join — rewrite if the subquery is large |
| `ObjectHashAggregate` or `ArrowEvalPython` nodes | Photon cannot accelerate these — check for Python UDFs, `TRANSFORM`/`FILTER` on arrays, or `MAP` operations |

After reading the plan, decide: **can you already identify the optimization, or do
you need more information about the tables?**

- If the bottleneck is clear (e.g. a correlated subquery, missing NULL filter,
  LOWER() on a filter column) — go straight to Phase 4.
- If the bottleneck depends on physical table properties (file size, partition
  columns, column cardinality) — collect stats for just those tables in 3.2.
- If a join target appears to be a view (plan shows a nested subquery or a
  `SubqueryAlias` node where you expect a FileScan) — read the view definition
  in 3.2 before deciding what to optimize.

### 3.2a Read view definitions (when a join target is a view)

The EXPLAIN plan will show a view's underlying query inlined as a subquery tree.
If you see a deep nested plan for what should be a simple table join, the view
itself may be the bottleneck — not the outer query.

To read the view definition:

```bash
$TUNE \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original "SHOW CREATE TABLE <view_name>" \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --explain-only
```

Or collect it alongside table stats (the `--table-stats` flag works for views too).

When you read a view definition, look for:
- Filters that could be pushed closer to the source scan
- Joins inside the view that are better placed in the outer query (where the
  caller already filters heavily before joining)
- Aggregations computed in the view that the caller immediately re-aggregates
- DISTINCT or ORDER BY inside the view that serve no purpose when used as a
  subquery
- Correlated subqueries or scalar subqueries that run once per row

**What to do if the view is suboptimal:**
You have two options — pick the one that is less invasive:

1. **Inline the view as a CTE** — replace `JOIN my_view ON ...` with
   `WITH my_view AS (<rewritten definition>) ...` in the optimized query.
   This avoids changing the view in the catalog and keeps the fix self-contained.

2. **Suggest a view rewrite** — if the view is used widely and inlining would
   make the outer query unreadable, write an optimized version of the view
   definition separately and note it under "Additional recommendations" in the
   final report. Do not change the view in the catalog.

Always prefer option 1 unless the view is complex enough that inlining it makes
the outer query harder to reason about than it was before.

### 3.2 Collect table stats (when needed)

Only run this step when the execution plan leaves a question that physical metadata
would answer. Pass only the tables relevant to the bottleneck — not every table in
the query.

```bash
$TUNE \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --table-stats <TABLE1> [<TABLE2> ...]
```

What this collects per table and when it matters:

| Section | Source | When you need it |
|:--------|:-------|:-----------------|
| **Schema** | `DESCRIBE table` | Partition columns unknown; filter pushdown uncertain |
| **Partition columns** | `DESCRIBE EXTENDED` | Plan shows FileScan without PartitionFilters |
| **Delta detail** | `DESCRIBE DETAIL` | Plan has SortMergeJoin — need sizeInBytes to decide BROADCAST |
| **Table stats** | `DESCRIBE EXTENDED` | Optimizer picked a bad join strategy; may have stale/missing stats |
| **Column stats** | `DESCRIBE EXTENDED t col` | High Exchange cost; need distinctCount/nullCount to assess skew |

Use these facts to make decisions:

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

---

## Phase 3.3 — Build an attack plan

Before writing a single line of optimized SQL, write a short numbered list of the
specific changes you intend to make and why. Show it to the user (or include it
in your reasoning) before proceeding to Phase 4.

Each item should name:
- **What** you will change (e.g. "replace SortMergeJoin with BROADCAST hint on `dim_country`")
- **Why** (e.g. "Delta detail shows sizeInBytes = 18 MB, well under the 200 MB threshold")
- **Expected effect** (e.g. "eliminates one Exchange shuffle node")

Example:

```
Attack plan:
1. Add /*+ BROADCAST(dim_country) */ — sizeInBytes 18 MB, plan currently SortMergeJoin → eliminates shuffle
2. Replace LOWER(email) = ? filter with COLLATE UTF8_LCASE — restores Delta file-skipping
3. Extract repeated subquery into CTE — currently executed once per row in the outer SELECT
4. Add IS NOT NULL guard on user_id before the JOIN — 12% null rate inflates shuffle size
```

If you have no concrete changes to make (the plan looks fine or the bottleneck is
outside SQL), say so explicitly and explain what you found.

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
- **Inlining a view as a CTE** — if a join target is a view whose definition is
  suboptimal, replace the view reference with `WITH view_name AS (<rewritten SQL>)`
  in the optimized query. The output is still a single self-contained SQL string.
- **Rewriting `IN (subquery)` as `EXISTS` or a semi-join** — Spark often builds a
  better plan for `EXISTS` / `LEFT SEMI JOIN` than for `IN` with a large subquery
- **Skew salting** — when a GROUP BY key is heavily skewed, a two-pass SQL salt
  distributes the hot partition across workers (see salting pattern below)

### Skew salting pattern

When the plan shows a highly skewed Exchange on a GROUP BY key, salt the aggregation:

```sql
-- Phase 1: aggregate with a random salt to spread the hot key
WITH salted AS (
  SELECT
    key,
    FLOOR(RAND() * 8) AS salt,  -- 8 buckets; tune to cluster core count
    SUM(value) AS partial_sum
  FROM large_table
  GROUP BY key, salt
)
-- Phase 2: collapse the salted buckets
SELECT key, SUM(partial_sum) AS total
FROM salted
GROUP BY key
```

Only use this when column stats or a skewed Exchange confirms one key dominates.
The extra aggregation pass adds overhead on balanced data — don't apply it speculatively.

### CTE materialization caveat

Spark does **not** guarantee that a CTE is computed only once. If a CTE is referenced
multiple times in the query, Spark may re-evaluate it on each reference. This means:

- A CTE used to "cache" an expensive subquery may not help — or may hurt if the
  subquery is scanned multiple times instead of once.
- If you add a CTE to de-duplicate a repeated subquery and the plan still shows the
  subquery running multiple times, note `CACHE TABLE` as a recommendation outside SQL scope.
- Prefer CTEs for readability and hint-targeting; don't assume they imply materialization.

### Photon-unfriendly patterns

Databricks Photon accelerates most SQL, but silently falls back to JVM execution for:

| Pattern | Why Photon can't accelerate it |
|:--------|:-------------------------------|
| Python / Scala UDFs | Black-box execution, no vectorization possible |
| `TRANSFORM(array, x -> ...)` | Higher-order functions not yet Photon-native |
| `FILTER(array, x -> ...)` | Same — lambda expressions bypass Photon |
| `MAP_KEYS` / `MAP_VALUES` on complex maps | Complex type operations not vectorized |
| Non-deterministic functions in certain contexts | Photon cannot reorder them safely |

If the plan shows `ArrowEvalPython`, `ObjectHashAggregate`, or `BatchEvalPython` nodes,
a Photon fallback is happening. Flag it in the attack plan and suggest replacing with
built-in Spark SQL equivalents where possible.

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

## Phase 5 — Validate, benchmark & log

### 5.1 Edit and commit

Edit `$QUERY_FILE` directly — the branch is isolated so edits are safe to make in place.

```bash
git add $QUERY_FILE
git commit -m "sql-tune: attempt <N> — <one-line description of what changed>"
```

Commit **before** benchmarking so every attempt is in the git log regardless of outcome.

### 5.2 Run the benchmark

```bash
$TUNE \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original @$QUERY_FILE \
  --optimized @$QUERY_FILE \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --n-runs <N_RUNS> > $LOG_FILE 2>&1
```

(Both `--original` and `--optimized` point to the same file — tune.py compares the
current version to the baseline it runs internally.)

The script outputs JSON with:
- `validation.passed` — whether results are byte-for-byte identical
- `validation.row_count` — number of rows compared
- `original.mean_s`, `original.std_s` — timing stats
- `optimized.mean_s`, `optimized.std_s` — timing stats
- `speedup` — ratio of original mean to optimized mean
- `statistically_significant` — true if optimized CI is entirely below original CI

### 5.3 Decide: keep or revert

A speedup is **real** only when:
1. `validation.passed = true` (identical results)
2. `speedup > 1.0` (optimized is faster on average)
3. `statistically_significant = true` (confidence intervals don't overlap)

```
✅ IMPROVED  → keep commit, update BEST_MEAN = optimized.mean_s
❌ SAME/WORSE → revert the file to the last kept commit:
               git checkout HEAD $QUERY_FILE
💥 VALIDATION FAIL → fix the query and re-benchmark before reverting
```

### 5.4 Log the attempt

Append to `$RESULTS_FILE`:

```
<N>	<commit-sha>	<optimized.mean_s>	<speedup>	<keep|discard>	<description>
```

If validation fails: fix the query and re-benchmark before doing anything else.

---

## Phase 5b — Autonomous optimization loop

Run continuously after the first benchmark. Never pause to ask "should I continue?".
Stop only when the user interrupts or explicitly says they're satisfied.

```
THINK   Read $RESULTS_FILE and the current best query.
        Study the EXPLAIN of the best query so far — not the original.
        Form a specific hypothesis: "changing X should reduce Y because Z."
        Follow the strategy priority below.

EDIT    Edit $QUERY_FILE directly — one focused change per attempt.
        The branch is isolated; edits are safe to make in place.

COMMIT  git add $QUERY_FILE && git commit -m "sql-tune: attempt <N> — <description>"
        Commit before benchmarking — this records what was tried.

RUN     $TUNE \
          --profile <PROFILE> --cluster-id <CLUSTER_ID> \
          --original @$ORIGINAL_FILE --optimized @$QUERY_FILE \
          --catalog <CATALOG> --schema <SCHEMA> \
          --n-runs <N_RUNS> > $LOG_FILE 2>&1

        # For simplicity / both goals, also score complexity
        python3 "$SKILL_DIR/scripts/complexity.py" --json $QUERY_FILE > complexity.json

MEASURE Extract from $LOG_FILE (timing) and complexity.json (score).
        On crash: read last 50 lines for the error. Attempt up to 2 quick fixes,
        amend the commit, re-run. If still broken, revert and discard.

        Metric to optimize depends on GOALS:
        ┌──────────────────────┬────────────────────────────────────────────────────┐
        │ speed                │ optimized.mean_s  (lower is better)                │
        │ simplicity           │ complexity score  (lower is better)                │
        │ speed,simplicity     │ Phase 1: optimize mean_s (same as speed)           │
        │                      │ Phase 2: once speed accepted, optimize score        │
        │                      │          while mean_s stays ≤ BEST_MEAN * 1.10     │
        └──────────────────────┴────────────────────────────────────────────────────┘

DECIDE  Compare metric to BEST:
        speed             → ✅ if mean_s improved + statistically significant
        simplicity        → ✅ if complexity score decreased + validation passes
        speed,simplicity  → phase 1: same as speed
                            phase 2: ✅ if score decreased AND mean_s ≤ BEST_MEAN * 1.10

        ❌ no improvement → git checkout HEAD $QUERY_FILE   (revert file, keep commit msg in log)
        💥 VALIDATION FAIL → fix semantics first, then re-benchmark

LOG     Append to $RESULTS_FILE:
        <N>\t<sha>\t<mean_s>\t<complexity_score>\t<status>\t<description>
```

### Strategy priority

1. **Follow the plan** — work through the attack plan from Phase 3.3 in order
2. **Follow wins** — if a hint or rewrite helped, probe further in that direction
3. **Diversify after 3 consecutive discards** — switch to a different bottleneck
4. **Combine winners** — if A and B each improved independently, try A+B together
5. **Diagnose no-speedup runs** — re-EXPLAIN the optimized query; check if AQE
   already did what the hint asked, or if a Photon fallback is dominating
6. **Accept the floor** — if 5+ consecutive attempts yield no improvement and the
   remaining ideas are speculative, stop the loop and go to Phase 6

**For `simplicity` or `speed,simplicity` goal**, strategy shifts focus (in the simplicity phase):
- Prefer removing CTEs that the optimizer re-evaluates anyway
- Inline single-use subqueries where they don't increase nesting
- Replace multi-step transformations with a single built-in function call
- Remove redundant ORDER BY, DISTINCT, or GROUP BY that the caller drops
- Simplicity wins don't require statistical significance — a lower score is enough

**Hard constraints that apply to all goals, including simplicity:**
- Never introduce `SELECT *` — explicit column lists must be preserved exactly.
  `SELECT *` hides schema changes, breaks downstream consumers, and can silently
  change column order. A query with fewer lines but a `SELECT *` is not simpler —
  it is fragile.
- Never remove columns from the output or reorder them
- Never change NULL semantics or filter behaviour

---

## Phase 6 — Report

Present a summary:

First print the full attempt log:

```bash
cat $RESULTS_FILE
```

Then show the git log of kept commits:

```bash
git log --oneline <baseline-sha>..HEAD
```

Then present the summary report:

```
## SQL Tuning Report

### Run summary
- Attempts: N total / K kept / M discarded
- Baseline: X.XXs  →  Best: X.XXs  (X.Xx speedup)

### Attempt log
| # | Mean (s) | Speedup | Status  | Description |
|:--|:---------|:--------|:--------|:------------|
| 0 | x.xx     | 1.0x    | baseline| original query |
| 1 | x.xx     | x.xx    | keep    | ... |
| 2 | x.xx     | x.xx    | discard | ... |

### Query plan bottlenecks (original)
<key findings from EXPLAIN>

### Optimizations applied (kept only)
1. <change — what + why>
...

### Original SQL
<original query>

### Optimized SQL
<best optimized query>

### Final benchmark
| Variant   | Mean (s) | Std (s) | Runs |
|:----------|:---------|:--------|:-----|
| Original  | x.xx     | x.xx    | N    |
| Optimized | x.xx     | x.xx    | N    |

Speedup: X.Xx  |  Statistically significant: yes/no
Validation: PASS — N rows, identical results

### Conclusion
<one paragraph: what changed, why it helped, any caveats>

### Additional recommendations (outside SQL scope)
<Z-ordering, ANALYZE TABLE, cluster sizing, etc. — if applicable>
```

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
