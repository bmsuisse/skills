# Eval 12 — Row Hash Validation on a 5B-Row Fact Table (with skill)

## Exact tune.py command

```bash
$TUNE \
  --profile prod \
  --cluster-id 0408-195905-abc \
  --original @fact_sales_5b_original.sql \
  --optimized @fact_sales_5b_optimized.sql \
  --catalog sales \
  --schema prod \
  --n-runs 3 \
  --timing-count \
  --compare-strategy row_hash
```

| Flag | Reason |
|:-----|:-------|
| `--timing-count` | Wraps timing in COUNT(*) — one integer per run to driver, eliminates OOM |
| `--compare-strategy row_hash` | SUM(xxhash64(all_cols)) on-cluster, two scalars to driver, zero rows collected |

## Why row_hash for 5B rows

SKILL.md defines four strategies by table size. At 5B rows, any strategy collecting rows OOMs the driver. `row_hash` avoids this: each variant computes `SUM(xxhash64(col1, col2, ...))` on-cluster, sends two scalars to the driver.

`checksum` not used — only covers numeric/boolean cols; would miss date_key/product_key if stored as strings/dates.

## Simulated Validation Output (strategy=row_hash)

```json
{
  "validation": {
    "strategy": "row_hash",
    "passed": true,
    "original_hash": 8471920374856201234,
    "optimized_hash": 8471920374856201234,
    "rows_collected_to_driver": 0
  }
}
```

```
[validate] Checking result equivalence (strategy=row_hash)...
[validate] PASS
  original_hash  = 8471920374856201234
  optimized_hash = 8471920374856201234
  rows collected to driver: 0
```

## Timing OOM handled with --timing-count

| Phase | Driver receives | OOM risk |
|:------|:----------------|:---------|
| Timing runs (--timing-count) | One integer per run | None |
| Validation (--compare-strategy row_hash) | Two scalar hashes total | None |

## Optimized SQL

```sql
SELECT
    d.date_key,
    p.product_key,
    SUM(f.sales_amount) AS revenue,
    COUNT(f.transaction_id) AS txn_count
FROM fact_sales_5b f
JOIN /*+ BROADCAST(d) */ dim_date d
    ON f.date_key = d.date_key
    AND d.year = 2024
JOIN /*+ BROADCAST(p) */ dim_product p
    ON f.product_key = p.product_key
GROUP BY
    d.date_key,
    p.product_key
```

Simulated: Baseline 312.4s → Best 47.8s (6.5x speedup). Validation: PASS (row_hash, 0 rows to driver).
