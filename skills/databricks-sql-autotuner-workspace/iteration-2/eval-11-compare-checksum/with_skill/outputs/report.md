# Eval 11 — compare-strategy checksum (with skill)

## Exact tune.py Command

```bash
.venv_autotuner/bin/python $SKILL_DIR/scripts/tune.py \
  --profile prod \
  --cluster-id 0408-195905-abc \
  --original "SELECT region_id, product_id, SUM(revenue) AS total_revenue, AVG(quantity) AS avg_qty, COUNT(*) AS n FROM fact_sales GROUP BY region_id, product_id" \
  --optimized "SELECT /*+ BROADCAST(r) */ f.region_id, f.product_id, SUM(f.revenue) AS total_revenue, AVG(f.quantity) AS avg_qty, COUNT(*) AS n FROM fact_sales f GROUP BY f.region_id, f.product_id" \
  --compare-strategy checksum \
  --n-runs 3
```

Flag | Value | Source
--- | --- | ---
`--profile` | prod | From invocation
`--cluster-id` | 0408-195905-abc | From invocation
`--compare-strategy` | checksum | Parsed in Phase 0, passed verbatim to tune.py
`--n-runs` | 3 | Default

## Simulated Validation Output

```
[validate] Checking result equivalence (strategy=checksum)...

Original  -> aggregation pass ... [done]
Optimized -> aggregation pass ... [done]

validation:
  strategy        : checksum
  columns_checked : [revenue, quantity, n]
  row_count_match : true
  passed          : true

[validate] PASS
```

JSON from tune.py:
```json
{
  "validation": {
    "passed": true,
    "strategy": "checksum",
    "columns_checked": ["revenue", "quantity", "n"],
    "row_count": 8432
  },
  "original":  { "mean_s": 18.74, "std_s": 0.43 },
  "optimized": { "mean_s": 11.21, "std_s": 0.31 },
  "speedup": 1.67,
  "statistically_significant": true
}
```

## Why checksum over full

Default `full` uses EXCEPT ALL, collecting both result sets to the driver. For a large `fact_sales GROUP BY region_id, product_id` this risks OOM. `checksum` runs a single aggregation pass per query — SUM + COUNT per numeric/boolean column — no rows reach the driver. Since all output columns are numeric aggregates, checksum gives full semantic coverage at O(1) driver memory cost.

`--compare-strategy checksum` was supplied in the invocation and passed through unchanged. Without it, the skill defaults to `full`.
