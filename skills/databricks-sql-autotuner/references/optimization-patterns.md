# Optimization Patterns Reference

Read this file at the start of Phase 4 (before writing the optimized query) and
when Phase 3.2a identifies a view as a join target.

---

## View optimization (Phase 3.2a)

The EXPLAIN plan inlines a view's underlying query as a subquery tree. If you see
a deep nested plan where you expect a FileScan, the join target is a view — and the
view itself may be the bottleneck.

Read the view definition:

```bash
$TUNE \
  --profile <PROFILE> \
  --cluster-id <CLUSTER_ID> \
  --original "SHOW CREATE TABLE <view_name>" \
  --catalog <CATALOG> \
  --schema <SCHEMA> \
  --explain-only
```

**What to look for inside the view definition:**
- Filters that could be pushed closer to the source scan
- Joins inside the view that are better placed in the outer query (where the caller
  already filters heavily before joining)
- Aggregations computed in the view that the caller immediately re-aggregates
- DISTINCT or ORDER BY inside the view that serve no purpose when used as a subquery
- Correlated or scalar subqueries that run once per row

**What to do:**

1. **Inline as a CTE** — replace `JOIN my_view ON ...` with
   `WITH my_view AS (<rewritten definition>) ...`. Self-contained, no catalog change.

2. **Suggest a view rewrite** — if the view is used widely and inlining would make
   the outer query unreadable, write an optimized version separately under
   "Additional recommendations" in the final report. Do not change the view in the catalog.

Prefer option 1 unless inlining makes the outer query harder to reason about.

---

## Skew salting

When the plan shows a heavily skewed Exchange on a GROUP BY key (one partition
vastly larger than the others), distribute the hot key with a two-pass salt:

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
The extra aggregation pass adds overhead on balanced data — don't apply speculatively.

---

## CTE materialization caveat

Spark does **not** guarantee that a CTE is computed only once. If a CTE is referenced
multiple times in the query, Spark may re-evaluate it on each reference. This means:

- A CTE used to "cache" an expensive subquery may not help — or may hurt if the
  subquery is scanned multiple times instead of once.
- If the plan still shows the subquery running multiple times after adding a CTE,
  note `CACHE TABLE` as a recommendation outside SQL scope.
- Prefer CTEs for readability and hint-targeting; don't assume they imply materialization.

---

## Photon-unfriendly patterns

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

---

## UNION ALL hint restriction

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

---

## Session UDF setup

If the query calls UDFs that are **not** persistent SQL functions in the catalog,
they must be registered at runtime. Create `udf_setup.py` in the current directory:

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

To distinguish persistent from session UDFs: persistent functions are created with
`CREATE FUNCTION` in the catalog and work as-is. Session UDFs exist only for the
duration of a Spark session and must be re-registered on each connection.

---

## Optimization loop strategy priority (Phase 5b)

1. **Follow the plan** — work through the attack plan from Phase 3.3 in order
2. **Follow wins** — if a hint or rewrite helped, probe further in that direction
3. **Diversify after 3 consecutive discards** — switch to a different bottleneck
4. **Combine winners** — if A and B each improved independently, try A+B together
5. **Diagnose no-speedup runs** — re-EXPLAIN the optimized query; check if AQE
   already did what the hint asked, or if a Photon fallback is dominating
6. **Accept the floor** — if 5+ consecutive attempts yield no improvement and the
   remaining ideas are speculative, stop and go to Phase 6

**For `simplicity` or `speed,simplicity` goal** (simplicity phase):
- Prefer removing CTEs that the optimizer re-evaluates anyway
- Inline single-use subqueries where they don't increase nesting
- Replace multi-step transformations with a single built-in function call
- Remove redundant ORDER BY, DISTINCT, or GROUP BY that the caller drops
- Simplicity wins don't require statistical significance — a lower score is enough

**Hard constraints (all goals including simplicity):**
- Never introduce `SELECT *` — explicit column lists must be preserved exactly
- Never remove columns from the output or reorder them
- Never change NULL semantics or filter behaviour
