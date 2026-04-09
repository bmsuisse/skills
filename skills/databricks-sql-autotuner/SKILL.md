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
| [`references/optimization-patterns.md`](references/optimization-patterns.md) | At the start of Phase 4, and whenever Phase 3.2a identifies a view as a join target. Contains: view inlining strategy, skew salting SQL, CTE materialization caveat, Photon-unfriendly patterns, UNION ALL hint restriction, session UDF setup, and the full optimization loop strategy. |
| [`references/sql-coding-guidelines.md`](references/sql-coding-guidelines.md) | When writing or rewriting any SQL — apply BME naming conventions, join style, CTE structure, alias patterns, and key naming rules to all generated SQL. Read at the start of Phase 4 alongside `optimization-patterns.md`. |

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
| `--timing-count` | `--timing-count` | Wrap timing runs in `COUNT(*)` to avoid collecting large result sets to the driver (use when query returns millions of rows) |
| `--global-temp` | `--global-temp` | Materialize results into cached global temp tables on the cluster (`global_temp._tuner_*`) instead of collecting to the driver. Applies to both timing and validation. Use when the result set is too large even for `COUNT(*)` or when you want to keep intermediate results on the cluster for inspection. |

The `--query` value:
- `@path/to/file.sql` → read the file
- Any other string → treat as inline SQL
- Omitted → ask the user to paste or provide the query

---

## Phase 1 — Environment discovery

Run `discover.py` to handle profile/cluster selection, DBR version detection, and
catalog/schema defaults in one step. It requires only the Databricks CLI — no venv needed.

```bash
python3 $SKILL_DIR/scripts/discover.py \
  [--profile <PROFILE>] \
  [--cluster-id <CLUSTER_ID> | --cluster-name <NAME>]
```

**Behaviour:**
- If only one CLI profile exists, auto-selects it; otherwise lists profiles and stops
  with `"status": "needs_profile"` — re-run with `--profile <name>`.
- If only one cluster is RUNNING, auto-selects it; otherwise lists usable clusters and
  stops with `"status": "needs_cluster"` — re-run with `--cluster-id <id>`.
- On success outputs `"status": "ok"` JSON with `profile`, `cluster_id`, `dbr_version`,
  `catalog`, `schema` — record all of these as session variables.
- If the cluster is TERMINATED, prints the start command; wait for it to reach RUNNING
  before proceeding.

If the CLI is not authenticated the command will fail — ask the user to run:
```bash
databricks auth login --profile <name>
```

After discovery, ask the user:
> **How many benchmark runs per variant? (default: 3, minimum: 2)**

Record as `N_RUNS`. Then present the full summary from the JSON and wait for confirmation.

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

Run `init_run.py` to handle branch creation, working-file setup, TSV initialisation,
and the baseline benchmark in one step. Must use the autotuner venv Python.

```bash
$VENV_PYTHON $SKILL_DIR/scripts/init_run.py \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original <@FILE_OR_INLINE_SQL> \
  [--optimized <out.sql>] \
  [--run-id <slug>] \
  [--n-runs <N_RUNS>] \
  [--catalog <CATALOG>] [--schema <SCHEMA>] \
  [--timing-count] [--global-temp]
```

**What it does:**
- Derives a `run-id` slug from the query filename (or timestamp for inline SQL); pass
  `--run-id` to override with a descriptive slug like `sales-summary`.
- Creates branch `sql-tune/<run-id>` and sets up `ORIGINAL_FILE` / `QUERY_FILE`
  (copies original → optimized file if `--optimized` is given).
- Excludes the TSV and log from git, writes the TSV header.
- Runs the baseline benchmark (original vs original) and appends attempt `0`.
- Outputs JSON with `run_id`, `baseline_mean_s`, `original_file`, `query_file`,
  `results_file`, `log_file`, `branch` — record all as session variables.

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

If the plan shows a deep nested subquery where you expect a FileScan, the join
target is a view. Read its definition with `SHOW CREATE TABLE <view_name>` via
`--explain-only`, or collect it alongside table stats (`--table-stats` works for views).

See **`references/optimization-patterns.md` → View optimization** for what to look
for inside the definition and whether to inline it as a CTE or suggest a separate rewrite.

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

Before writing the optimized query, read **`references/optimization-patterns.md`** for
detailed patterns: skew salting SQL, CTE materialization caveats, Photon-unfriendly
patterns, UNION ALL hint restrictions, and session UDF setup.

### What is NOT allowed — never suggest these

- `spark.conf.set(...)` or any cluster/session configuration
- DataFrame / PySpark API code (`.filter()`, `.join()`, `.groupBy()`, etc.)
- DDL changes (`ALTER TABLE`, `OPTIMIZE`, `ZORDER`, `VACUUM`, `ANALYZE TABLE`)
- Any rewrite that changes columns, row count, or values in the output

If a non-SQL improvement (e.g., Z-ordering, cluster sizing) would help, mention it
separately under "Additional recommendations (outside scope)" in the final report —
but never include it in the optimized query itself.

### Hint restriction — CRITICAL for UNION ALL

Spark SQL does **not** allow hints inside CTE branches that are part of a `UNION ALL`.
Place all optimizer hints on the **outermost SELECT only**. See
`references/optimization-patterns.md` → UNION ALL hint restriction for examples.

### UDF handling

If the query calls UDFs: persistent catalog functions (`CREATE FUNCTION`) work as-is.
Session UDFs must be registered via `udf_setup.py` — see
`references/optimization-patterns.md` → Session UDF setup.

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

See **`references/optimization-patterns.md` → Optimization loop strategy priority**
for the full prioritized list, per-goal tactics, and hard constraints (including the
`SELECT *` prohibition).

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
| `discover.py` prints `needs_profile` or `needs_cluster` | Normal — re-run with the missing `--profile` or `--cluster-id` flag |
| `Cluster not found` | Verify cluster ID: `python3 $SKILL_DIR/scripts/discover.py --profile <PROFILE>` |
| Version mismatch | Ensure `DBR_VERSION` from `discover.py` matches installed `databricks-connect` |
| `.venv_autotuner` import errors | Delete the venv and re-run `env_setup.py` |
| `init_run.py` branch already exists | Pass a different `--run-id` or delete the branch first |
| Validation diff on floats | May be floating-point non-determinism — check with `ROUND()` or cast to DECIMAL |
| `.collect()` fails with `>4 GiB` / driver OOM | Query returns millions of rows — add `--timing-count` to wrap timing runs in `COUNT(*)`. Validation still uses real results. For very large datasets use `--global-temp` instead, which keeps all intermediate results on the cluster. |
| Hint parse error in UNION ALL | Move hint to outermost SELECT (see Phase 4 restriction) |
| Session UDF not found | Create `udf_setup.py` with a `register_udfs(spark)` function |
