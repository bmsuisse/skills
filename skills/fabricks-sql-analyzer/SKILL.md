---
name: fabricks-sql-analyzer
description: Analyzes all SQL files in the Fabricks.Runtime repository, builds a dependency DAG, runs performance heuristics, and produces a Markdown report with ranked findings and improvement suggestions. Optionally fetches row counts and EXPLAIN COST plans from Databricks. Pass --fix to automatically create a branch and apply SQL rewrites.
---

# Fabricks SQL Analyzer

You are a Spark/Databricks SQL performance expert. Your job is to run the dependency analyzer script, interpret its output, produce a thorough Markdown report, and — when requested — apply the fixes directly to the SQL files on a dedicated branch.

> **See also**: The `sql-optimization` skill (`bmsuisse/skills/sql-optimization`) provides the universal SQL optimization reference (patterns, anti-patterns, index design, pagination, etc.) that underpins the recommendations made here.

## Parsing user arguments

The user may pass arguments after the skill name, e.g.:

```
/fabricks-sql-analyzer --fix
/fabricks-sql-analyzer --fix --top 10
/fabricks-sql-analyzer --fix --branch perf/my-branch
/fabricks-sql-analyzer --top 30 --explain
/fabricks-sql-analyzer --all-files --score-threshold 50
```

Extract these from the invocation:

| Argument | Default | Meaning |
|---|---|---|
| `--fix` | off | Create a branch and apply SQL rewrites after the report |
| `--fix-top N` | 10 | When fixing, only fix the top-N tables by impact score (avoids huge PRs) |
| `--branch NAME` | `perf/sql-fixes-YYYY-MM-DD` | Git branch name to create when `--fix` is set |
| `--top N` | 20 | How many most-depended-upon tables to analyze |
| `--all-files` | off | Analyze every SQL file, not just the top-N most depended-upon |
| `--score-threshold N` | 0 | Skip tables with `impact_score` below N |
| `--explain` | off | Fetch `EXPLAIN COST` plans from Databricks |
| `--profile NAME` | `premium` | Databricks CLI profile |
| `--ancestors TABLE` | off | Print transitive dependencies of a single table and stop |

---

## Step 0 — Ensure Databricks CLI is installed and authenticated

Do this before running the analyzer script. Skip any sub-step that is already satisfied.

### 0a — Check installation

```bash
databricks -v
```

- If it prints a version number, skip to **0b**.
- If the command is not found, install it:

**macOS/Linux (Homebrew — preferred):**
```bash
brew tap databricks/tap && brew install databricks
```

**Linux fallback (no sudo):**
```bash
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
```

### 0b — Check authentication for the target profile

The default profile is `premium` (overridable via `--profile`). Check whether it is valid:

```bash
databricks auth profiles
```

- If the target profile is listed with `Valid: YES`, skip to **Step 1**.
- If the profile is listed but `Valid: NO`, re-authenticate:
  ```bash
  databricks auth login --host <workspace-url> --profile premium
  ```
- If the profile does not exist at all, ask the user for their workspace URL, then authenticate:
  ```bash
  databricks auth login --host <workspace-url> --profile premium
  ```

**Authentication opens a browser (OAuth — never use PATs).** After the browser flow the CLI prints `Profile premium was successfully saved`.

**Verify** with a lightweight command before proceeding:
```bash
databricks current-user me --profile premium
```

If this fails, do not proceed to Step 1 — surface the error to the user.

---

## Step 1 — Run the script

The analyzer script lives at `.agents/skills/fabricks-sql-analyzer/sql_dependency_analyzer.py`.
Run it from the **repository root** so that `ROOT = Path(__file__).parent.parent.parent.parent` resolves correctly.

```bash
uv run python .agents/skills/fabricks-sql-analyzer/sql_dependency_analyzer.py \
    --top 20 \
    --row-counts \
    --json /tmp/fabricks_analysis.json
```

`--row-counts` is always included by default (fetches live `COUNT(*)` from Databricks to weight severity by table size).

Additional flags the user may request:
- `--explain` — fetch `EXPLAIN COST` plans from Databricks
- `--profile <name>` — Databricks CLI profile (default: `premium`)
- `--ancestors <table>` — print transitive dependencies of a single table and stop
- `--top N` — change how many tables are ranked (default 20)
- `--all-files` — analyze every SQL file regardless of dependency rank
- `--score-threshold N` — only report tables with impact_score ≥ N

Parse the JSON output file for structured data. Also capture stdout for the dependency ranking table and graph stats.

---

## Step 2 — Produce the Markdown report

Generate a report using the structure below. Fill every section with real findings from the script output; never leave placeholder text.

---

```markdown
# Fabricks SQL Dependency & Performance Report
_Generated: {date}_

## Executive Summary

| Metric | Value |
|--------|-------|
| SQL files scanned | … |
| Graph nodes | … |
| Graph edges | … |
| Weakly connected components | … |
| Dependency cycles detected | … |
| Tables analyzed | … |

> **Key finding**: One-sentence summary of the most critical issue found.

---

## Dependency Hotspots

Tables with the highest number of dependents are the most critical to optimize — a performance problem here cascades to every downstream job.

| Rank | Table | Dependents | Row Count | Impact Score | Warnings |
|------|-------|-----------|-----------|-------------|----------|
| 1 | … | … | … | … | … |
| … | … | … | … | … | … |

> Tables are sorted by **impact_score** = (dependents × 10) + (row_count_millions × 5) + severity_sum.

---

## Performance Findings

For each table with at least one warning, include a sub-section:

### `{rank}. schema.table_name` ({N} dependents, impact: {score})

**Source**: `gold/step/topic/item.sql`

#### Detected Issues

| Severity | Pattern | Description |
|----------|---------|-------------|
| ⚠️ High | SELECT * | Avoid SELECT * — select only needed columns to reduce shuffle/IO |
| … | … | … |

#### Recommended Fix

Provide a concrete, Spark SQL–idiomatic rewrite or refactoring advice.
Reference the Fabricks step layer (staging / raw / transf / core / semantic) when relevant.
Prefer:
- CTEs over repeated subqueries
- `LEFT ANTI JOIN` over `NOT IN (SELECT …)`
- `LEFT SEMI JOIN` or `EXISTS` over `WHERE x IN (SELECT …)`
- Column pruning (`SELECT col1, col2`) over `SELECT *`
- `GROUP BY ALL` over `SELECT DISTINCT`
- Upstream filtering before `EXPLODE`
- Exact matches / bloom filters instead of `LIKE '%val%'` / `ILIKE` on large tables
- Splitting `OR` join conditions into `UNION ALL`
- Casting join keys in a upstream CTE instead of inside the ON clause
- Replacing `array_contains` in JOIN ON with a lateral explode + equi-join
- **Collations** instead of `LOWER(col) = LOWER('val')` or `ILIKE` for case/accent-insensitive comparisons — define the column with `COLLATE UTF8_LCASE` (English) or `COLLATE <LANG>_AI` (language-specific accent-insensitive) and write a plain equality filter; this enables Delta file-skipping and can yield up to 22× faster queries vs. wrapping in `LOWER()`. Run `ANALYZE TABLE … COMPUTE STATISTICS FOR COLUMNS …` after altering collation. Available since Databricks Runtime 13.3+ (GA in DBR 17.3).

If an `EXPLAIN COST` plan is available, highlight the most expensive nodes (high `rowCount`, `dataSize`, or `numPartitions`) and suggest partition pruning or Z-ordering.

---

## Tables with No Issues

List tables in the top-N that passed all heuristics — short, one line each.

---

## Dependency Cycles

If cycles > 0, list them and explain the risk (infinite pipeline loops, stale data).

---

## Recommendations Summary

Ordered by expected impact (highest impact_score first):

1. **[Critical]** …
2. **[High]** …
3. **[Medium]** …
4. …

---

## Next Steps

- Run with `--explain` to get query cost breakdowns for the worst offenders.
- Use `--ancestors <table>` to trace the full upstream dependency chain of any hotspot.
- After applying fixes, re-run the analyzer to confirm warning counts and impact scores drop.
- Consider **Z-ORDER BY** on frequently filtered columns for the largest Delta tables.
- Consider **Liquid Clustering** (Databricks Runtime 13.3+) on hot tables instead of static partitioning.
- Use **ANALYZE TABLE … COMPUTE STATISTICS** on staging/raw tables to improve the Spark optimizer's cardinality estimates.
- Consider **Collations** (`UTF8_LCASE` for English, language codes like `DE`/`FR`/`EL_AI` for others) on string columns that are filtered or joined with case/accent-insensitive comparisons. Eliminates `LOWER()` wrappers, enables Delta file-skipping, and can deliver up to **22× faster** queries (GA since Databricks Runtime 17.3). List available collations with `SELECT * FROM collations()`.
- For general SQL optimization patterns (index design, pagination, JOIN tuning, batch ops), refer to the **`sql-optimization`** skill.
```

---

## Step 3 — Apply fixes (only when `--fix` is present)

**Skip this step entirely if `--fix` was not passed.**

When `--fix` is requested, after completing the report, apply the SQL rewrites directly to the repository.

### 3a — Create a branch

```bash
git checkout -b <branch-name>
```

Use the `--branch` value if supplied, otherwise default to `perf/sql-fixes-YYYY-MM-DD` (use today's date).

### 3b — Determine which files to fix

Take the results from the JSON output, already sorted by descending `impact_score`:

```
impact_score = (dependent_count × 10) + (row_count_millions × 5) + severity_sum
```

Limit to `--fix-top N` tables (default 10) to keep the diff reviewable.

### 3c — Apply fixes file by file

For each file in the fix list:

1. **Read** the current SQL content.
2. **Apply** every applicable fix from the table below using the Edit tool.
3. **Format** the file after editing: `uv run sqlfmt <file>`
4. **Verify** the rewrite preserves the original query semantics.

#### Fix catalogue

Apply **only** the fixes that correspond to warnings actually detected in that file. Never invent new changes.

| Warning | Fix to apply |
|---|---|
| `SELECT DISTINCT` | Replace `SELECT DISTINCT` with `SELECT` + add `GROUP BY ALL` at the end of the query/subquery |
| `NOT IN subquery` | Rewrite `WHERE x NOT IN (SELECT y FROM t)` as `LEFT ANTI JOIN t ON x = t.y` |
| `IN subquery` | Rewrite `WHERE x IN (SELECT y FROM t)` as `LEFT SEMI JOIN t ON x = t.y` or `WHERE EXISTS (SELECT 1 FROM t WHERE …)` |
| `Repeated scan` (≥2×) | Introduce a CTE at the top: `WITH <alias> AS (SELECT … FROM <table>)` and replace all inline references |
| `OR in JOIN condition` | Split `JOIN t ON a.k = t.k OR a.k2 = t.k2` into two branches combined with `UNION ALL` (deduplicate if needed) |
| `Subquery in SELECT` | Rewrite as a CTE + `LEFT JOIN`, moving the correlated subquery into an aggregation CTE |
| `EXPLODE` | Add a `WHERE` filter CTE before the `EXPLODE` to reduce row count first |
| `SELECT *` on gold layer | Replace with an explicit column list drawn from columns actually produced by upstream sources — if the full column list cannot be determined statically, leave a `-- TODO: replace SELECT * with explicit columns` comment and skip the rewrite |
| `UDF in WHERE/JOIN` | Replace with a built-in Spark SQL equivalent when the replacement is unambiguous (e.g., `udf_lower(x)` → `LOWER(x)`); otherwise leave a `-- TODO: replace UDF with built-in` comment |
| `LIKE %val%` | Only rewrite if a clear prefix-only pattern is evident; leave other cases unchanged |
| `ILIKE` | Rewrite as `LOWER(col) LIKE LOWER('pattern')` where safe; or, if the column is a string column used repeatedly for case-insensitive comparison, recommend setting `COLLATE UTF8_LCASE` on the column (see Collation tip below) |
| `LOWER() comparison` | Rewrite `LOWER(col) = LOWER('val')` (or `LOWER(col) = 'val'`) by setting `COLLATE UTF8_LCASE` on the column and using a plain equality: `col = 'val'`. This unlocks Delta file-skipping and Photon optimization, yielding up to 22× speedup. Requires `ALTER TABLE … ALTER COLUMN … TYPE STRING COLLATE UTF8_LCASE` followed by `ANALYZE TABLE … COMPUTE STATISTICS FOR COLUMNS …`. Use language-specific collations (e.g., `DE`, `FR`, `EL_AI`) when sorting/comparing non-English text. |
| `CAST on JOIN key` | Move the CAST into an upstream CTE so the join key is a plain column reference |
| `array_contains in JOIN` | Rewrite as a `LATERAL VIEW EXPLODE` + equi-join, or filter before the join using a semi-join |
| `Implicit cross join` | Rewrite `FROM a, b WHERE a.k = b.k` as `FROM a JOIN b ON a.k = b.k` |
| `Unbounded window frame` | Remove the explicit `ROWS/RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` if the default frame is equivalent, or narrow to `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` where semantics allow |

**Safety rules:**
- Preserve all existing comments and formatting style.
- Do not rename columns, add/remove columns, or change output schema.
- Do not change the output table name or Fabricks step/topic/item path.
- If a fix would require schema knowledge you do not have, leave a `-- TODO:` comment instead of guessing.
- If a file has multiple warnings, apply all applicable fixes in a single Edit pass.
- Always run `uv run sqlfmt <file>` after editing to preserve consistent formatting.

### 3d — Commit

After all files are edited and formatted, stage and commit:

```bash
git add <file1> <file2> …
git commit -m "perf: apply SQL performance fixes to top-<N> hotspot tables

Automated fixes applied by fabricks-sql-analyzer:
- <table1>: <list of fixes applied>
- <table2>: <list of fixes applied>
…

Co-Authored-By: antigravity <noreply@google.com>"
```

### 3e — Report what was done

After committing, append a **## Applied Fixes** section to the report listing:

- The branch name
- Each file touched, the warnings it had, and which fixes were applied vs skipped (with reason)
- Any `-- TODO:` comments left behind and why

---

## Behavior guidelines

- Be specific: quote the actual table names, file paths, and warning messages from the script output.
- Severity mapping (for human reporting): `CROSS JOIN` = Critical; `Implicit cross join` = Critical; `NOT IN subquery` = High; `OR in JOIN` = High; `Subquery in SELECT` = High; `CAST on JOIN key` = High; `IN subquery` = Medium; `Unbounded window frame` = Medium; `SELECT *` = Medium; `Repeated scan` = Medium; `EXPLODE` = Medium; `UDF in WHERE/JOIN` = Medium; `array_contains in JOIN` = Medium; `LOWER() comparison` = Medium; `SELECT DISTINCT` = Low; `LIKE %val%` = Low; `ILIKE` = Low.
- If Databricks row counts are available, factor table size into severity (a `SELECT *` on a 1 B-row table is Critical).
- Report tables sorted by `impact_score` descending — the JSON is already sorted.
- Keep code examples in `spark` dialect (Spark SQL).
- Do not invent findings — only report what the script actually detected.
- When applying fixes, do not silently skip a file — always report whether each fix was applied or left as a TODO.
