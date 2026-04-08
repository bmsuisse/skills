# Spark SQL Performance Tuning Reference

Source: https://spark.apache.org/docs/latest/sql-performance-tuning.html  
Relevant for: SQL-level query optimization on Databricks (Spark 3.x / 4.x)

---

## Join Strategy Hints (use directly in SQL)

These are the only hints that belong in the optimized query:

```sql
SELECT /*+ BROADCAST(t) */ ...         -- force broadcast join (alias: BROADCASTJOIN, MAPJOIN)
SELECT /*+ MERGE(t) */ ...             -- force sort-merge join
SELECT /*+ SHUFFLE_HASH(t) */ ...      -- force shuffle-hash join
SELECT /*+ SHUFFLE_REPLICATE_NL(t) */ ... -- force nested-loop join (use with caution)
```

**Hint priority (when conflicting hints exist):**  
`BROADCAST` > `MERGE` > `SHUFFLE_HASH` > `SHUFFLE_REPLICATE_NL`

**When to use which:**

| Strategy | When to apply |
|:---------|:-------------|
| `BROADCAST(t)` | `t` is small (< 200 MB on Databricks, default threshold is 10 MB for open-source Spark). Check `DESCRIBE DETAIL` sizeInBytes. |
| `MERGE(t)` | Large-to-large join, data is already sorted on join key, or you want predictable memory usage |
| `SHUFFLE_HASH(t)` | One side fits in memory but is too big for broadcast; avoids sort cost of MERGE |
| No hint | Let AQE decide — usually best unless AQE is making a wrong decision |

---

## Partitioning Hints (use in SQL)

Control output file count or repartition for downstream efficiency:

```sql
SELECT /*+ COALESCE(3) */ * FROM t              -- reduce to N partitions (no shuffle)
SELECT /*+ REPARTITION(3) */ * FROM t           -- repartition to N (full shuffle)
SELECT /*+ REPARTITION(col) */ * FROM t         -- repartition by column
SELECT /*+ REPARTITION(3, col) */ * FROM t      -- repartition to N by column
SELECT /*+ REPARTITION_BY_RANGE(col) */ * FROM t
SELECT /*+ REBALANCE */ * FROM t                -- balance output file sizes (AQE)
SELECT /*+ REBALANCE(col) */ * FROM t
```

---

## Adaptive Query Execution (AQE) — enabled by default on Databricks

AQE re-optimizes the plan at runtime using actual row counts and sizes. You generally don't need to fight it — but knowing what it does helps you write SQL that works with it.

| AQE feature | What it does | SQL impact |
|:------------|:------------|:----------|
| Coalesce shuffle partitions | Merges small post-shuffle partitions | Reduces task overhead on GROUP BY / JOIN |
| Dynamic broadcast join | Converts SortMergeJoin → BroadcastHashJoin at runtime if a side turns out small | Even without a BROADCAST hint, small tables get broadcast |
| Skew join optimization | Splits skewed partitions automatically | Helps when one GROUP BY key has far more rows than others |
| Shuffle hash join conversion | Converts SortMergeJoin → ShuffledHashJoin if one side fits in memory | Avoids sort cost |

**Key AQE config (informational — do not change in SQL):**

| Config | Default | Note |
|:-------|:--------|:-----|
| `spark.sql.adaptive.enabled` | `true` | On by default in Spark 3.2+ / Databricks |
| `spark.sql.autoBroadcastJoinThreshold` | 10 MB (open-source) / ~200 MB (Databricks Photon) | Tables smaller than this are broadcast automatically |
| `spark.sql.adaptive.autoBroadcastJoinThreshold` | same as above | AQE-specific override |
| `spark.sql.shuffle.partitions` | 200 | Default post-shuffle partition count; AQE coalesces from this |
| `spark.sql.adaptive.advisoryPartitionSizeInBytes` | 64 MB | Target partition size after AQE coalescing |
| `spark.sql.adaptive.skewJoin.skewedPartitionFactor` | 5.0 | A partition is skewed if it's 5× the median |

---

## Statistics and the Optimizer

The Spark optimizer uses table/column statistics to pick join strategies. If stats are stale or missing, it falls back to pessimistic estimates — which often produces SortMergeJoin when BroadcastHashJoin would be better.

**How to check if stats exist:**
```sql
DESCRIBE EXTENDED catalog.schema.table
-- Look for: Statistics: X bytes, Y rows
-- If missing → stats have never been computed or are stale
```

**How stats get computed (outside SQL scope — note as recommendation):**
```sql
-- Whole table stats (row count + size)
ANALYZE TABLE catalog.schema.table COMPUTE STATISTICS

-- Column-level stats (min, max, distinct count, null count)
ANALYZE TABLE catalog.schema.table COMPUTE STATISTICS FOR COLUMNS col1, col2

-- All columns
ANALYZE TABLE catalog.schema.table COMPUTE STATISTICS FOR ALL COLUMNS
```

*Note: ANALYZE TABLE is a DDL operation — do not include it in the optimized query.  
Mention it in "Additional recommendations (outside scope)" if stats appear to be missing.*

---

## Key Numbers to Know

| Threshold | Value | What it means |
|:----------|:------|:-------------|
| Default broadcast threshold (open-source Spark) | 10 MB | Tables smaller than this auto-broadcast |
| Databricks Photon effective broadcast threshold | ~200 MB | Databricks raises this significantly |
| AQE advisory partition size | 64 MB | Target post-shuffle partition size |
| Skew detection multiplier | 5× median | A partition is skewed if 5× larger than median |
| Default shuffle partitions | 200 | Starting point for post-shuffle tasks |

---

## SQL-Level Optimization Checklist

Use this when analyzing the query and execution plan:

- [ ] **Join order**: Put the larger table first in FROM, filter small tables in CTEs before joining
- [ ] **Broadcast eligibility**: Check `DESCRIBE DETAIL` sizeInBytes vs autoBroadcastJoinThreshold
- [ ] **Predicate pushdown**: Filters on partition columns should appear in the plan as `PartitionFilters`, not `PushedFilters` after the scan
- [ ] **Correlated subqueries**: Replace with JOIN or window function — correlated subqueries run once per row
- [ ] **DISTINCT vs GROUP BY**: `GROUP BY` is generally more efficient; `DISTINCT` may not hint at the optimizer's aggregation strategy
- [ ] **CTE vs subquery**: CTEs with clear names help the optimizer use them as hint targets (for BROADCAST)
- [ ] **UNION vs UNION ALL**: `UNION` adds a dedup pass — use `UNION ALL` if duplicates are impossible or acceptable
- [ ] **NULL handling in joins**: `NULL != NULL` in SQL — if join keys can be NULL, add `IS NOT NULL` filters before the join to reduce shuffle size
- [ ] **Skew**: If one GROUP BY key dominates, consider salting or filtering it to a separate branch
- [ ] **UDFs**: Session UDFs are black boxes — no pushdown, no optimization. Consider replacing with built-in functions or CTEs that compute once
- [ ] **Case-insensitive string filters**: Using `LOWER(col) = 'abc'` prevents Delta file-skipping and disables Photon acceleration. Use collation instead (see Collation section below)

---

## Collations — Case-Insensitive Queries

Collations enable case-insensitive comparisons **natively in SQL** without wrapping columns in `LOWER()` or `UPPER()`. This is a significant SQL-level optimization on Databricks.

### Why it matters

| Approach | Effect |
|:---------|:-------|
| `LOWER(col) = 'abc'` | Applies a function per row → Delta file-skipping disabled, Photon cannot accelerate, full scan |
| `col = 'abc' COLLATE UTF8_LCASE` or collated column | Preserves Delta min/max stats → file-skipping works, Photon accelerates the comparison |

Benchmarks: **up to 22x faster** on 1B strings for equality filter; **10x faster** for `STARTSWITH`/`ENDSWITH`/`CONTAINS` with Photon.

### Syntax

```sql
-- Inline collation on a literal comparison
SELECT * FROM t WHERE col = 'abc' COLLATE UTF8_LCASE;

-- Apply collation to a column expression
SELECT * FROM t WHERE COLLATE(col, 'UTF8_LCASE') = 'abc';

-- Declare collation at table definition (preferred — enables file-skipping automatically)
CREATE TABLE t (col STRING COLLATE UTF8_LCASE, ...);

-- Quick test
SELECT 'hello' COLLATE UTF8_LCASE = 'HELLO';  -- returns true
```

### Common collations

| Collation | Behaviour |
|:----------|:----------|
| `UTF8_BINARY` | Default. Case-sensitive, byte-comparison. Fastest for exact matches. |
| `UTF8_LCASE` | Case-insensitive. Photon-accelerated on Databricks. Use for case-insensitive string filters. |
| `UNICODE` | Unicode-aware case-sensitive comparison |
| `UNICODE_CI` | Unicode-aware case-insensitive comparison |

### When to suggest (as SQL optimization)

- Query has `LOWER(col) = ?` or `UPPER(col) = ?` in WHERE, JOIN, or HAVING
- Query has `CONTAINS(LOWER(col), ?)`, `STARTSWITH(LOWER(col), ?)`, etc.
- Column stores user-input strings where case varies (names, emails, product codes)

Replace the function-wrapped filter with a collation expression — same semantics, dramatically better performance. This is a pure SQL change with no cluster or schema modification required when used inline.
