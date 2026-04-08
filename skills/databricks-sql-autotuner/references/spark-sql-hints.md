# Spark SQL Hints Reference

Source: https://spark.apache.org/docs/latest/sql-ref-syntax-qry-select-hints.html  
Syntax: `/*+ hint [, hint2, ...] */` immediately after SELECT

---

## Join Hints

### BROADCAST (alias: BROADCASTJOIN, MAPJOIN)

Force the named table to be broadcast to all executors instead of shuffled.

```sql
SELECT /*+ BROADCAST(t1) */ * FROM t1 INNER JOIN t2 ON t1.key = t2.key;
SELECT /*+ BROADCASTJOIN(t1) */ * FROM t1 LEFT JOIN t2 ON t1.key = t2.key;
SELECT /*+ MAPJOIN(t2) */ * FROM t1 RIGHT JOIN t2 ON t1.key = t2.key;
```

- Ignores `autoBroadcastJoinThreshold` — forces broadcast regardless of size
- If both sides are hinted BROADCAST, the smaller side (by stats) is chosen
- Use when: the table is small enough to fit in executor memory (check `DESCRIBE DETAIL` sizeInBytes)

### MERGE (alias: SHUFFLE_MERGE, MERGEJOIN)

Force sort-merge join. Both sides are shuffled and sorted on the join key.

```sql
SELECT /*+ MERGE(t1) */ * FROM t1 INNER JOIN t2 ON t1.key = t2.key;
SELECT /*+ SHUFFLE_MERGE(t1) */ * FROM t1 INNER JOIN t2 ON t1.key = t2.key;
SELECT /*+ MERGEJOIN(t2) */ * FROM t1 INNER JOIN t2 ON t1.key = t2.key;
```

- Predictable memory usage (streaming read, no build side)
- Good default for large-to-large joins where AQE keeps choosing wrong strategy

### SHUFFLE_HASH

Force shuffle hash join. One side is shuffled and used as a build-side hash table.

```sql
SELECT /*+ SHUFFLE_HASH(t1) */ * FROM t1 INNER JOIN t2 ON t1.key = t2.key;
```

- Avoids the sort cost of MERGE
- Build side must fit in memory
- If both sides are hinted, smaller side (by stats) becomes build side

### SHUFFLE_REPLICATE_NL

Force shuffle-and-replicate nested loop join.

```sql
SELECT /*+ SHUFFLE_REPLICATE_NL(t1) */ * FROM t1 INNER JOIN t2 ON t1.key = t2.key;
```

- For non-equi joins (no ON condition or inequality conditions)
- Generally the slowest strategy — only use when no equi-join key exists

### Hint Priority (highest → lowest)
`BROADCAST` > `MERGE` > `SHUFFLE_HASH` > `SHUFFLE_REPLICATE_NL`

Conflicting hints: higher-priority hint wins, lower-priority hint generates a warning and is ignored.

---

## Partitioning Hints

### COALESCE

Reduce the number of output partitions **without a shuffle**.

```sql
SELECT /*+ COALESCE(3) */ * FROM t;
```

- Only reduces, never increases partition count
- No data movement — fastest option when writing fewer files

### REPARTITION

Repartition to a new count or by column(s), **with a full shuffle**.

```sql
SELECT /*+ REPARTITION(3) */ * FROM t;            -- to N partitions
SELECT /*+ REPARTITION(c) */ * FROM t;            -- by column (hash)
SELECT /*+ REPARTITION(3, c) */ * FROM t;         -- N partitions, by column
```

- Full shuffle — use when you need uniform distribution by a specific key
- Useful before a wide aggregation to control parallelism

### REPARTITION_BY_RANGE

Repartition by range (sorted order) rather than hash.

```sql
SELECT /*+ REPARTITION_BY_RANGE(c) */ * FROM t;
SELECT /*+ REPARTITION_BY_RANGE(3, c) */ * FROM t;
```

- Useful when writing range-partitioned output for sorted reads

### REBALANCE

Balance output partition sizes (split skewed, merge small). Requires AQE.

```sql
SELECT /*+ REBALANCE */ * FROM t;
SELECT /*+ REBALANCE(3) */ * FROM t;
SELECT /*+ REBALANCE(c) */ * FROM t;
SELECT /*+ REBALANCE(3, c) */ * FROM t;
```

- Best-effort: splits skewed partitions, merges tiny ones
- Ideal when writing query results to a Delta table to avoid small files

---

## Multiple Hints in One Query

Multiple hints can appear in a single `/*+ ... */` block or in multiple blocks:

```sql
-- Multiple join hints (only the highest priority one applies per join pair)
SELECT /*+ BROADCAST(t1), MERGE(t2) */ * FROM t1 JOIN t2 ON t1.k = t2.k;

-- Multiple partitioning hints (leftmost wins)
SELECT /*+ REPARTITION(100), COALESCE(500) */ * FROM t;
-- → REPARTITION(100) is applied; COALESCE is ignored
```

---

## UNION ALL and Hint Scoping — CRITICAL

**Each branch of a UNION ALL is an independent query block.**  
Hints in one branch do NOT propagate to other branches.

```sql
-- ❌ WRONG: hint only applies to the first SELECT, archive branch has no hint
SELECT /*+ BROADCAST(dim) */ a.id, dim.name
FROM fact_current a JOIN dim ON a.dim_id = dim.id
UNION ALL
SELECT a.id, dim.name
FROM fact_archive a JOIN dim ON a.dim_id = dim.id   -- SortMergeJoin here!

-- ✅ CORRECT: each branch carries its own hint
SELECT /*+ BROADCAST(dim) */ a.id, dim.name
FROM fact_current a JOIN dim ON a.dim_id = dim.id
UNION ALL
SELECT /*+ BROADCAST(dim) */ a.id, dim.name
FROM fact_archive a JOIN dim ON a.dim_id = dim.id

-- ✅ ALSO CORRECT: wrap in CTE, place hint on outermost SELECT
WITH current AS (SELECT * FROM fact_current WHERE ...),
     archive AS (SELECT * FROM fact_archive WHERE ...)
SELECT /*+ BROADCAST(dim) */ c.id, dim.name FROM current c JOIN dim ON c.dim_id = dim.id
UNION ALL
SELECT /*+ BROADCAST(dim) */ a.id, dim.name FROM archive a JOIN dim ON a.dim_id = dim.id
```

Similarly, hints inside a CTE branch only apply within that CTE's scope — not to queries that reference the CTE from outside.

---

## Quick Decision Guide

| Situation | Hint to use |
|:----------|:-----------|
| One join side is small (< ~200 MB on Databricks) | `BROADCAST(small_table)` |
| Large-to-large join, AQE picks wrong strategy | `MERGE(either_table)` |
| Medium table, want to avoid sort cost | `SHUFFLE_HASH(smaller_table)` |
| Non-equi join (no equality condition) | `SHUFFLE_REPLICATE_NL(smaller_table)` |
| Writing output with skewed partitions | `REBALANCE` |
| Reducing output files (no shuffle) | `COALESCE(n)` |
| Full repartition by key for downstream reads | `REPARTITION(n, col)` |
