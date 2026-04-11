# Eval Report: databricks-sql-autotuner --compare-strategy checksum

**Date:** 2026-04-11
**Eval:** eval-11-compare-checksum
**Mode:** without_skill (no skill document referenced)

---

## Task Parameters

- `--compare-strategy`: checksum
- `--profile`: prod
- `--cluster-id`: 0408-195905-abc
- `--original`: `SELECT region_id, product_id, SUM(revenue) AS total_revenue, AVG(quantity) AS avg_qty, COUNT(*) AS n FROM fact_sales GROUP BY region_id, product_id`
- `--optimized`: `SELECT /*+ BROADCAST(r) */ f.region_id, f.product_id, SUM(f.revenue) AS total_revenue, AVG(f.quantity) AS avg_qty, COUNT(*) AS n FROM fact_sales f GROUP BY f.region_id, f.product_id`

---

## Exact tune.py Command I Would Run

Based on general knowledge of how a Databricks SQL autotuner tool would work, I would run:

```bash
python tune.py \
  --profile prod \
  --cluster-id 0408-195905-abc \
  --compare-strategy checksum \
  --original "SELECT region_id, product_id, SUM(revenue) AS total_revenue, AVG(quantity) AS avg_qty, COUNT(*) AS n FROM fact_sales GROUP BY region_id, product_id" \
  --optimized "SELECT /*+ BROADCAST(r) */ f.region_id, f.product_id, SUM(f.revenue) AS total_revenue, AVG(f.quantity) AS avg_qty, COUNT(*) AS n FROM fact_sales f GROUP BY f.region_id, f.product_id"
```

### Reasoning for Flags

- `--profile prod`: Selects the `prod` Databricks CLI profile from `~/.databrickscfg`.
- `--cluster-id 0408-195905-abc`: Targets the specific interactive cluster.
- `--compare-strategy checksum`: Validates result equivalence via checksum rather than row-count or full diff.
- `--original` / `--optimized`: The two SQL queries to compare.

---

## What --compare-strategy checksum Does

**My knowledge level: Partial / Inferred — no skill document read**

I do not have built-in knowledge of this specific `tune.py` tool. Based on general SQL tooling patterns:

1. Both queries are executed against the same cluster.
2. The result sets are hashed (e.g., MD5 or SHA over all rows/columns).
3. Checksums are compared — a match means the optimized query is semantically equivalent.
4. Advantage over row-count: catches value-level differences, not just cardinality differences.
5. Advantage over full diff: avoids downloading all rows; only one hash value per query is needed.

Likely implementation: wrapping each query in a `checksum()`/`hash()` aggregate over all output columns, possibly with a deterministic sort applied first to handle ordering differences.

---

## Simulated Validation Output

```
[databricks-sql-autotuner] Starting comparison...
  Profile  : prod
  Cluster  : 0408-195905-abc
  Strategy : checksum

[1/4] Connecting to cluster 0408-195905-abc via profile 'prod'... OK
[2/4] Executing ORIGINAL query...
      Rows returned : 184,320
      Execution time: 47.3s
      Checksum      : a3f9c21d7e004b82
[3/4] Executing OPTIMIZED query...
      Rows returned : 184,320
      Execution time: 12.8s
      Checksum      : a3f9c21d7e004b82

[4/4] Comparing checksums...
      ORIGINAL  checksum: a3f9c21d7e004b82
      OPTIMIZED checksum: a3f9c21d7e004b82
      Result: MATCH

=============================================
  VALIDATION PASSED — queries are equivalent
=============================================

Performance Summary:
  Original  execution time : 47.3s
  Optimized execution time : 12.8s
  Speedup                  : 3.70x
  Time saved               : 34.5s

Recommendation: APPROVED — optimized query is safe to promote.
```

---

## Key Observations About the Queries

1. **BROADCAST hint alias mismatch**: `/*+ BROADCAST(r) */` references alias `r`, but no table in the optimized query is aliased as `r`. The only alias present is `f` for `fact_sales`. This is a likely bug in the optimized query — the hint would be silently ignored by Spark.

2. **Alias addition**: `fact_sales f` is cosmetically different but functionally equivalent to `fact_sales`.

3. **Column qualification**: `f.region_id` etc. replace unqualified names — equivalent in a single-table query.

4. **Aggregate functions**: Identical in both queries.

5. **GROUP BY**: Equivalent grouping keys.

---

## Confidence Assessment

| Aspect | Confidence | Notes |
|---|---|---|
| tune.py command flags | Medium | Inferred from task parameters and CLI conventions |
| --compare-strategy checksum behavior | Medium | Inferred from general SQL tooling; no skill doc read |
| Simulated output format | Low | Entirely fabricated for illustration; actual format unknown |
| BROADCAST(r) alias mismatch | High | Directly observable from the provided SQL |

---

## Summary

Without the skill document, I was able to construct a plausible `tune.py` command, reason about what `--compare-strategy checksum` likely means, identify a potential bug in the optimized query (BROADCAST hint references non-existent alias `r`), and produce a simulated output.

I was not able to know the exact CLI interface, flag names, output format, or whether checksum is computed client-side or via a Databricks SQL aggregate function.
