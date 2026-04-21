---
name: coding-guidelines-sql
description: >
  SQL and data warehouse coding guidelines for the BME data platform. Use
  whenever writing, reviewing, or refactoring SQL — including SparkSQL, T-SQL,
  and Databricks SQL. Apply when naming tables, columns, CTEs, views, functions,
  or procedures; building fact or dimension tables; working with business keys,
  surrogate keys, or metadata columns; or setting up the semantic layer. Also
  apply for Spark SQL: QUALIFY, GROUP BY ALL, collations, NULL-safe patterns,
  conditional aggregation, timestamp intervals.
  Trigger on: "write sql", "review sql", "fact table", "dimension table",
  "surrogate key", "business key", "gold layer", "spark sql", "databricks sql",
  "t-sql", "naming convention", "sql style", "semantic layer", "combi field",
  "qualify", "group by all", "deduplication", "conditional aggregation".
---

# SQL Coding Guidelines

These conventions apply to all SQL written on the BME data platform (SparkSQL,
Databricks SQL, T-SQL). The goal is consistency across layers and teams — when
in doubt, follow the principle of least surprise: names should be readable,
predictable, and close to the source system.

---

## General Rules

- **English only** — all identifiers, comments, and aliases.
- **Lowercase** — keywords, identifiers, aliases, CTE names.
- **Snake case** — `sales_amount`, `order_backlog`, not `SalesAmount`.
- **Singular** — `sales_order`, `sales_date`, not `sales_orders`.
- **Double quotes** for string literals.
- **Backticks** (`` ` ``) for special-character identifiers in SparkSQL / sink targets — these are excluded from SQL formatting tools.
- **Square brackets** (`[]`) for special-character identifiers in legacy T-SQL only.

---

## Column Naming

### General
- Keep names close to the source: `order_nr`, `customer_nr`, `row_type_id`, `appointment_uuid`.
- Be specific: `start_call_date`, not `date`.
- Avoid `_name` suffix — use the concept directly: `cost_center`, not `cost_center_name`.

### Prefixes and Suffixes
| Pattern | Meaning | Example |
|---|---|---|
| `_sk` | Surrogate key in fact table | `cost_center_sk` |
| `_hsk` | Historized surrogate key in fact table | `item_hsk` |
| `_bk` | Business key in fact table | `item_bk` |
| `_key` | Business key in dimension (gold) | `item_key` |
| `_identity` | Identity / sequence key | `_identity` |
| `_metadata` | Metadata struct column | `_metadata` |
| `_` prefix | Internal / derived columns | `_pre_calculation`, `_sales_without_tax` |
| `is_` prefix | Boolean flag | `is_transfer_order`, `is_inter_company` |
| `nr` | Abbreviation for "number" | `order_nr` |

### Flags
Flags must be boolean. In SparkSQL, `1 == 1` evaluates to `true`, so:
```sql
-- correct
is_inter_company = true

-- avoid
is_inter_company = 1
```

### Abbreviation: nr
Use `nr` for "number", not `num` or `no`:
```sql
order_nr, customer_nr   -- correct
order_num, order_no     -- avoid
```

---

## Keys

### Business Key Logic
Build business keys using `concat_ws` with a coalesce fallback of `"-2"` for null-safe uniqueness:
```sql
concat_ws("*", coalesce(field_a, "-2"), coalesce(field_b, "-2")) as item_key
```

### Business Key Naming
- **In dimension (gold):** suffix `_key`, column is the identifier in that dimension.
  ```sql
  concat_ws("*", coalesce(item_nr, "-2")) as item_key
  ```
- **In fact:** prefix with the dimension table name, suffix `_bk`.
  ```sql
  -- dim_item → item_bk
  item_bk
  cost_center_bk
  ```
- If a business key is a **concatenation of multiple source keys**, keep it denormalized in the fact table (don't collapse it) — this aids debugging.
- Always include business keys in fact tables even when you also have the surrogate key — they're essential for debugging.

### Surrogate Key Join Pattern
Join to a dimension on **all parts of the business key** to resolve the surrogate key:
```sql
left join dim_item di
  on lower(f.item_bk) = lower(di.item_key)
```

### Identity Key
`_identity` is provided by the framework unless the column is explicitly named `_identity` and is a `bigint`, in which case it can be overwritten.

---

## SQL Style

### Joins
- Use `left join`, not `left outer join`.
- Always write `inner join` explicitly — not just `join`.
- Normalize join keys to lowercase: `lower(bk) = lower(bk)`.
- Use meaningful, snake_case aliases:
  ```sql
  from fact_sales fs
  inner join dim_cost_center cc
      on lower(fs.cost_center_bk) = lower(cc.cost_center_key)
  left join dim_item i
      on lower(fs.item_bk) = lower(i.item_key)
  ```
- Alias names: `order_line`, `order_header`, `cc` for cost center — be descriptive, not cryptic.

### Unions
When unioning tables from different sources, add a `_source` column to identify the origin:
```sql
select
    order_nr,
    "calenso" as _source
from calenso_orders

union all

select
    order_nr,
    "sws" as _source
from sws_orders
```

### Subqueries
Avoid subqueries. Use CTEs instead — they are easier to read, debug, and reuse.

### Layer Direction
Always build forward through the layers. Gold relies on transform; transform relies on raw. Never create backward dependencies (a transform layer table must not query a gold layer table).

---

## CTEs

Prefer CTEs over subqueries and over repeating logic:
- Define logic once in a CTE; reference the result downstream.
- CTE names: snake_case, descriptive — `sales_pre_calc`, `order_base`, `cost_allocation`.
- Do not nest subqueries inside CTEs.

```sql
with order_base as (
    select
        order_nr,
        customer_nr,
        order_date,
        amount * 1.0 as sales_amount
    from raw_orders
),

sales_pre_calc as (
    select
        ob.*,
        sales_amount - discount as net_sales_amount
    from order_base ob
)

select *
from sales_pre_calc
```

---

## Object Naming

| Object | Prefix | Example |
|---|---|---|
| Function | `f_` or `udf_` | `f_get_fiscal_year`, `udf_normalize_key` |
| View | `v_` | `v_sales_summary` |
| Stored procedure | `sp_` | `sp_load_fact_sales` |

---

## Comments

Add comments only when they convey information that isn't obvious from the code — primarily business logic that can't be expressed in a good alias or CTE name. Good aliases and CTE names are the primary documentation tool.

Column-level comment syntax (TBD):
```sql
/* This is the sales amount including tax */ sales_amount_gross
```

---

## Metadata

Every managed table includes a `_metadata` struct column provided by the framework. Do not manually construct or overwrite it unless specifically required.

---

## Semantic Layer

The semantic layer (e.g. for PowerBI or other BI tools) is the **only place** where display formatting and combi fields are built. Do not duplicate this logic in upstream layers or inside PowerBI itself.

### Combi Fields
Combine the name and the identifier in a standard format:
```
Geberit Vertriebs AG (00008465)
```

Name the field after the concept, not the combination:
```sql
-- correct: field is named after the dimension concept
"Supplier"

-- avoid
"Supplier Name + Number"
```

### Simple Derived Fields
Simple boolean displays, flag labels, and formatting are also built in the semantic layer, not in PowerBI measures.

---

## BME Reference

Refer to the internal naming convention document **04.02 Naming conventions for tables and fields** for any cases not covered here.

---

## SparkSQL Best Practices

These patterns apply specifically to SparkSQL / Databricks SQL. They make queries
faster, safer, and more readable — use them whenever the target platform is Spark.

### Lateral Column Alias — reuse SELECT expressions without a subquery

Databricks SQL supports referencing an alias defined earlier in the same `SELECT`
clause — no subquery or CTE needed.
See: https://www.databricks.com/blog/introducing-support-lateral-column-alias

```sql
-- avoid: repeating the expression or wrapping in a subquery
select
    sales_amount - discount as net_amount,
    (sales_amount - discount) * 0.1 as tax_amount   -- expression repeated
from fact_sales

-- prefer: lateral column alias
select
    sales_amount - discount as net_amount,
    net_amount * 0.1 as tax_amount                   -- reuses the alias directly
from fact_sales
```

Also useful for computed boolean flags that feed a subsequent filter:

```sql
select
    order_date,
    fiscal_year,
    (sales_amount > 1000) as is_high_value,
    is_high_value and fiscal_year = 2024 as is_current_high_value
from fact_sales
```

### QUALIFY — deduplication and top-N without a wrapper CTE

`QUALIFY` filters window function results inline. It eliminates the extra CTE you'd
otherwise need just to filter on `row_number()`.
See: https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify

```sql
-- avoid: extra CTE just to filter the window result
with ranked as (
    select
        order_nr,
        customer_nr,
        order_date,
        row_number() over (partition by customer_nr order by order_date desc) as rn
    from fact_sales
)
select order_nr, customer_nr, order_date
from ranked
where rn = 1

-- prefer: QUALIFY keeps it in one step
select order_nr, customer_nr, order_date
from fact_sales
qualify row_number() over (partition by customer_nr order by order_date desc) = 1
```

Works with `rank()`, `dense_rank()`, and any other window function.

### GROUP BY ALL — clean aggregations

`GROUP BY ALL` groups by every non-aggregate column automatically. No need to
repeat every dimension column in the `GROUP BY` clause.

```sql
-- avoid: repeating all dimension columns
select
    cost_center,
    region,
    fiscal_year,
    sum(sales_amount) as total_sales
from fact_sales
group by cost_center, region, fiscal_year

-- prefer: GROUP BY ALL
select
    cost_center,
    region,
    fiscal_year,
    sum(sales_amount) as total_sales
from fact_sales
group by all
```

### Collations — case-insensitive joins without `lower()`

Wrapping a column in `lower()` disables Delta file-skipping and prevents Photon
from optimizing the filter. Set a collation on the column once; use plain equality
forever after.

```sql
-- avoid: lower() breaks file-skipping, forces full scan
where lower(item_bk) = lower(item_key)

-- prefer: set collation once on the column (one-time DDL)
alter table dim_item alter column item_key type string collate utf8_lcase;

-- then join with plain equality — file-skipping works, Photon can optimize
left join dim_item i
    on f.item_bk = i.item_key
```

When collation is not possible (e.g. source tables you don't own), use `lower()` on
both sides consistently — as already defined in the join style rules above.

Common collations:

| Collation | Use case |
|---|---|
| `utf8_lcase` | English case-insensitive (default choice) |
| `de`, `fr`, `el` | Language-specific ordering |
| `el_ai`, `fr_ai` | Accent-insensitive variants |

### Boolean expressions as aliases

In SparkSQL a comparison expression returns `true`/`false` directly. No `CASE WHEN`
needed to produce a boolean column.

```sql
-- avoid
case when sales_amount > 1000 then true else false end as is_high_value

-- prefer
(sales_amount > 1000) as is_high_value
```

This is consistent with the flag convention (`is_` prefix, boolean type).

### FILTER (WHERE …) — conditional aggregation

Cleaner than `count(case when … end)` and composes better with `group by all`.

```sql
-- avoid
count(case when is_transfer_order then 1 end) as transfer_order_count

-- prefer
count(*) filter (where is_transfer_order) as transfer_order_count
```

### NOT EXISTS over NOT IN — null safety

`NOT IN` returns zero rows if any value in the subquery is `NULL`. `NOT EXISTS` is
null-safe and typically produces a better execution plan.

```sql
-- avoid: returns nothing if any customer_nr is null
where customer_nr not in (select customer_nr from blocked_customers)

-- prefer
where not exists (
    select 1
    from blocked_customers bc
    where bc.customer_nr = f.customer_nr
)
```

### EXISTS over COUNT(*) > 0

`EXISTS` stops at the first match. `COUNT(*) > 0` scans all matching rows first.

```sql
-- avoid
where (select count(*) from fact_sales fs where fs.customer_nr = d.customer_nr) > 0

-- prefer
where exists (select 1 from fact_sales fs where fs.customer_nr = d.customer_nr)
```

### Timestamp intervals — `>=` / `<` over BETWEEN

`BETWEEN` is inclusive on both ends and behaves unexpectedly with timestamps.
Use a half-open interval instead.

```sql
-- avoid: '2024-01-31 12:00:00' may be excluded depending on precision
where order_date between "2024-01-01" and "2024-01-31"

-- prefer: half-open interval, always correct
where order_date >= "2024-01-01"
  and order_date < "2024-02-01"
```

### Prefer `spark.sql()` over the PySpark DataFrame API

When writing Python code that queries data on Databricks, `spark.sql()` is easier
to read, review, and optimize than chained DataFrame methods. The SQL can also be
pasted directly into a notebook for debugging.

```python
# prefer
result = spark.sql("""
    select customer_nr, sum(sales_amount) as total_sales
    from fact_sales
    where fiscal_year = 2024
    group by all
""")

# avoid for plain data queries
result = df.filter(F.col("fiscal_year") == 2024) \
           .groupBy("customer_nr") \
           .agg(F.sum("sales_amount").alias("total_sales"))
```

Reserve the DataFrame API for cases where SQL is genuinely awkward: ML pipelines,
UDF registration, or dynamic column lists.
