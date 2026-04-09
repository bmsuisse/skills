# SQL Coding Guidelines (BME)

Apply these conventions to all SQL written or rewritten by the autotuner.

---

## General

- English only.
- Lowercase — keywords, identifiers, aliases, CTE names.
- Snake case — `sales_amount`, `order_backlog`.
- Singular — `sales_order`, not `sales_orders`.
- Double quotes for string literals.
- Backticks (`` ` ``) for special-character identifiers in SparkSQL / sink targets (excluded from SQL formatters).
- `[]` for special-character identifiers in legacy T-SQL only.

---

## Column Naming

| Pattern | Meaning | Example |
|---|---|---|
| `_sk` | Surrogate key in fact | `cost_center_sk` |
| `_hsk` | Historized surrogate key in fact | `item_hsk` |
| `_bk` | Business key in fact | `item_bk` |
| `_key` | Business key in dimension (gold) | `item_key` |
| `_identity` | Identity / sequence key | `_identity` |
| `_metadata` | Metadata struct column | `_metadata` |
| `_` prefix | Internal / derived columns | `_pre_calculation` |
| `is_` prefix | Boolean flag | `is_transfer_order` |
| `nr` | Abbreviation for "number" | `order_nr` |

- Avoid `_name` suffix — use the concept directly: `cost_center`, not `cost_center_name`.
- Keep names close to the source: `order_nr`, `customer_nr`, `row_type_id`, `appointment_uuid`.
- Be specific: `start_call_date`, not `date`.
- Flags are boolean: `is_inter_company = true` (in SparkSQL `1 == 1` returns `true`).

---

## Keys

### Business key construction
```sql
concat_ws("*", coalesce(field_a, "-2"), coalesce(field_b, "-2")) as item_key
```

### Business key naming
- Dimension (gold): `_key` suffix — `item_key`, `cost_center_key`.
- Fact: `<dim_table>_bk` — `dim_item` → `item_bk`, `dim_cost_center` → `cost_center_bk`.
- If a business key is a concatenation of multiple source keys, keep it denormalized in the fact.
- Always include business keys in fact tables alongside surrogate keys (aids debugging).

### Surrogate key join pattern
Join on all parts of the business key, normalized to lowercase:
```sql
left join dim_item i
    on lower(f.item_bk) = lower(i.item_key)
```

---

## SQL Style

- `left join`, not `left outer join`.
- Always write `inner join` explicitly — not just `join`.
- Normalize join keys to lowercase: `lower(bk) = lower(bk)`.
- Use meaningful snake_case aliases: `order_line`, `order_header`, `cc` for cost center.
- Comments only for business logic that can't be expressed in a good alias or CTE name.
- Define logic once in a CTE; reference the result downstream — avoid repeating expressions.
- Avoid subqueries; use CTEs.
- Always build forward through the layers (gold → transf → raw, never backwards).

---

## CTEs

- Snake_case, descriptive names: `sales_pre_calc`, `order_base`, `cost_allocation`.
- No nested subqueries inside CTEs.

```sql
with order_base as (
    select
        order_nr,
        amount * 1.0 as sales_amount
    from raw_orders
),

sales_pre_calc as (
    select
        ob.*,
        sales_amount - discount as net_sales_amount
    from order_base ob
)

select * from sales_pre_calc
```

---

## Unions

Add `_source` column to identify the origin table:
```sql
select order_nr, "calenso" as _source from calenso_orders
union all
select order_nr, "sws"     as _source from sws_orders
```

---

## Object Naming

| Object | Prefix | Example |
|---|---|---|
| Function | `f_` or `udf_` | `f_get_fiscal_year` |
| View | `v_` | `v_sales_summary` |
| Stored procedure | `sp_` | `sp_load_fact_sales` |

---

## Semantic Layer

- Combi fields are built here, not in PowerBI.
- Name fields after the concept: `"Supplier"`, not `"Supplier Name + Number"`.
- Format: Name followed by number in brackets — `Geberit Vertriebs AG (00008465)`.

---

## SparkSQL Best Practices

### Lateral Column Alias — reuse SELECT expressions without a subquery
Databricks SQL lets you reference an alias defined earlier in the same `SELECT` — no subquery needed.
See: https://www.databricks.com/blog/introducing-support-lateral-column-alias
```sql
-- prefer: reuse alias directly
select
    sales_amount - discount as net_amount,
    net_amount * 0.1 as tax_amount      -- lateral alias, no repeated expression
from fact_sales
```
When rewriting a query: replace repeated expressions and subquery wrappers with lateral column aliases where the same value is computed more than once in a SELECT.

### QUALIFY — deduplication / top-N without a wrapper CTE
`QUALIFY` filters window function results inline — eliminates a wrapper CTE just for `WHERE rn = 1`.
See: https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify
```sql
-- prefer over row_number() CTE wrappers
select order_nr, customer_nr, order_date
from fact_sales
qualify row_number() over (partition by customer_nr order by order_date desc) = 1
```

### GROUP BY ALL
```sql
select cost_center, region, fiscal_year, sum(sales_amount) as total_sales
from fact_sales
group by all
```

### Collations — case-insensitive joins without `lower()`
`lower()` disables Delta file-skipping. Set collation once on the column instead:
```sql
alter table dim_item alter column item_key type string collate utf8_lcase;
-- then use plain equality in joins — file-skipping and Photon both work
```
Use `lower()` only when you don't own the source table.

### Boolean expressions as aliases
```sql
-- prefer
(sales_amount > 1000) as is_high_value

-- avoid
case when sales_amount > 1000 then true else false end as is_high_value
```

### FILTER (WHERE …) — conditional aggregation
```sql
count(*) filter (where is_transfer_order) as transfer_order_count
-- over: count(case when is_transfer_order then 1 end)
```

### NOT EXISTS over NOT IN
`NOT IN` silently returns no rows when any subquery value is `NULL`. Use `NOT EXISTS`.

### EXISTS over COUNT(*) > 0
`EXISTS` stops at the first match; `COUNT(*) > 0` scans everything first.

### Timestamp intervals — `>=` / `<` over BETWEEN
```sql
-- prefer: half-open interval
where order_date >= "2024-01-01" and order_date < "2024-02-01"
-- avoid: BETWEEN is inclusive on both ends, behaves unexpectedly with timestamps
```
