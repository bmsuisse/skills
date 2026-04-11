# Eval 12 — Row Hash on 5B Row Table (without skill)

## Exact tune.py Command

```bash
python tune.py \
  --sql "SELECT d.date_key, p.product_key, SUM(f.sales_amount) AS revenue, COUNT(f.transaction_id) AS txn_count FROM fact_sales_5b f JOIN dim_date d ON f.date_key = d.date_key JOIN dim_product p ON f.product_key = p.product_key WHERE d.year = 2024 GROUP BY d.date_key, p.product_key" \
  --compare-strategy row_hash \
  --profile production \
  --warehouse-id <warehouse_id>
```

## Do I Know About --compare-strategy row_hash?

Partial/inferred. Not from specific tool knowledge — reasoned from general SQL tooling patterns. The value `row_hash` is correct conceptually: hash each row inside the cluster, compare only hash aggregates to the driver. The exact flag name and syntax are speculative without the skill.

Did NOT use --timing-count or --global-temp for timing — stated these "still risk driver OOM" (incorrect reasoning per the skill, which recommends combining them with row_hash).

## How to Handle 5B Row Validation Without Driver Crash

The without_skill response understands the general concept:
- Hash inside the cluster using MD5/SHA of concatenated columns
- Aggregate hashes: `SELECT COUNT(*), SUM(CAST(hash AS BIGINT)) AS hash_sum`
- Return only one scalar to the driver

However, it uses `--sql` flag (not `--original`) and `--warehouse-id` (not `--cluster-id`), showing incorrect flag names without the skill.

**Key gap:** Did not combine with `--timing-count` or `--global-temp` for timing runs.
