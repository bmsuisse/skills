---
name: sql-optimization
description: "Universal SQL performance optimization assistant for comprehensive query tuning, indexing strategies, and database performance analysis across all SQL databases (MySQL, PostgreSQL, SQL Server, Oracle, Databricks). SQL style: sqlfmt lowercase, CTEs over subqueries, QUALIFY over row_number subqueries, GROUP BY ALL, meaningful aliases, alias-prefixed columns, no select *."
---

# SQL Performance Optimization Assistant

Expert SQL performance optimization for ${selection} (or entire project if no selection). Focus on universal SQL optimization techniques that work across MySQL, PostgreSQL, SQL Server, Oracle, and other SQL databases.

**Formatting and style rules applied throughout this skill:**

- **ANSI SQL first**: prefer standard ANSI-92/SQL:2003 constructs that work across all databases. Vendor-specific extensions (`qualify`, `group by all`, Databricks collations, `explain cost`) are used only where they offer a clear, significant benefit and are **explicitly labelled** with the supported platform.
- **SQL** — formatted with [`sqlfmt`](https://sqlfmt.com) (`line_length = 119`):
  - All keywords lowercase (`select`, `from`, `where`, `join`, `with`, …)
  - ANSI join syntax (`inner join`, `left join`) — never implicit comma joins
  - CTEs (`with … as (…)`) instead of subqueries or derived tables
  - One clause per line, 4-space indentation inside CTEs
  - Trailing commas on column lists
- **Python** — formatted with [`ruff`](https://docs.astral.sh/ruff/) (`line-length = 119`, `target-version = "py312"`):
  - Apply `ruff format` + `ruff check --fix` to any Python that embeds or generates SQL
  - SQL strings inside Python still follow sqlfmt conventions

- **Naming and clarity:**
  - ❌ `select *` — always list explicit columns
  - ❌ Single-letter aliases (`a`, `b`, `c`) — use meaningful names (`ord`, `cust`, `prod`)
  - ✅ Prefix every selected column with its table alias: `ord.id`, `cust.name`
  - ✅ Backticks for identifiers with spaces or reserved words: `` `my name` ``, `` `order` `` — **never** single quotes
  - ✅ Single quotes for string literals only: `'active'`, `'2024-01-01'`
  - ✅ `qualify` instead of `row_number()` CTE wrappers — _Databricks SQL / DuckDB / BigQuery / Snowflake_
  - ✅ `group by all` for clean aggregations — _Databricks SQL / DuckDB / Spark SQL 3.4+_

---

## 🎯 Core Optimization Areas

### Query Performance Analysis

```sql
-- ❌ bad: select *, function on column breaks index, IN subquery
select *
from orders
where year(created_at) = 2024
    and customer_id in (select id from customers where status = 'active');

-- ✅ good: explicit columns, meaningful aliases, CTE, range predicate
with active_customers as (
    select cust.id
    from customers as cust
    where cust.status = 'active'
),
orders_2024 as (
    select
        ord.id,
        ord.customer_id,
        ord.total_amount,
        ord.created_at,
    from orders as ord
    inner join active_customers as cust on ord.customer_id = cust.id
    where ord.created_at >= '2024-01-01'
        and ord.created_at < '2025-01-01'
)
select
    ord.id,
    ord.customer_id,
    ord.total_amount,
    ord.created_at,
from orders_2024 as ord;

-- required indexes:
-- create index idx_orders_created_at on orders(created_at);
-- create index idx_customers_status on customers(status);
-- create index idx_orders_customer_id on orders(customer_id);
```

### Index Strategy Optimization

```sql
-- ❌ bad: over-indexed, wrong column order
create index idx_user_data on users(email, first_name, last_name, created_at);

-- ✅ good: purpose-built composite indexes
create index idx_users_email_created on users(email, created_at);
create index idx_users_name on users(last_name, first_name);

-- partial index for selective predicate
create index idx_users_active on users(status, created_at)
where status is not null;
```

### CTE over Subquery / Correlated Subquery

```sql
-- ❌ bad: correlated subquery — re-executes for every row
select prod.product_name, prod.price
from products as prod
where prod.price > (
    select avg(p2.price) from products as p2 where p2.category_id = prod.category_id
);

-- ✅ good: CTE + window function — single pass, no subquery
with products_with_avg as (
    select
        prod.product_name,
        prod.price,
        avg(prod.price) over (partition by prod.category_id) as avg_category_price,
    from products as prod
)
select
    pwa.product_name,
    pwa.price,
from products_with_avg as pwa
where pwa.price > pwa.avg_category_price;
```

---

## 📊 Performance Tuning Techniques

### JOIN Optimization

```sql
-- ❌ bad: select *, left joins where inner suffices, late filter, no column aliases
select o.*, c.name, p.product_name
from orders o
left join customers c on o.customer_id = c.id
left join order_items oi on o.id = oi.order_id
left join products p on oi.product_id = p.id
where o.created_at > '2024-01-01'
    and c.status = 'active';

-- ✅ good: explicit columns, meaningful aliases, filter pushed into CTE
with recent_orders as (
    select ord.id, ord.total_amount, ord.customer_id
    from orders as ord
    where ord.created_at > '2024-01-01'
)
select
    ord.id,
    ord.total_amount,
    cust.name,
    prod.product_name,
from recent_orders as ord
inner join customers as cust on ord.customer_id = cust.id and cust.status = 'active'
inner join order_items as items on ord.id = items.order_id
inner join products as prod on items.product_id = prod.id;
```

### Pagination Optimization

```sql
-- ❌ bad: offset-based — full scan up to offset position
select
    prod.id,
    prod.name,
    prod.created_at,
from products as prod
order by prod.created_at desc
limit 20 offset 10000;

-- ✅ good: cursor-based — index seek on created_at
select
    prod.id,
    prod.name,
    prod.created_at,
from products as prod
where prod.created_at < '2024-06-15 10:30:00'
order by prod.created_at desc
limit 20;
```

### Aggregation — GROUP BY ALL

```sql
-- ❌ bad: repeating every dimension column in group by
select
    ord.customer_id,
    cust.region,
    cust.segment,
    count(*) as order_count,
    sum(ord.total_amount) as revenue,
from orders as ord
inner join customers as cust on ord.customer_id = cust.id
group by ord.customer_id, cust.region, cust.segment;

-- ✅ good: group by all — groups by every non-aggregate column automatically
-- (Databricks SQL, DuckDB, Spark SQL 3.4+)
select
    ord.customer_id,
    cust.region,
    cust.segment,
    count(*) as order_count,
    sum(ord.total_amount) as revenue,
from orders as ord
inner join customers as cust on ord.customer_id = cust.id
group by all;

-- conditional aggregation with group by all
select
    ord.status,
    count(*) as total_orders,
    count(case when ord.priority = 'high' then 1 end) as high_priority_count,
    sum(ord.total_amount) as total_revenue,
from orders as ord
group by all;
```

---

## 🔍 Query Anti-Patterns and Fixes

### No SELECT \* — Explicit Columns with Alias Prefix

```sql
-- ❌ bad: select * — fetches all columns, breaks on schema changes, hides intent
select *
from orders as ord
join customers as cust on ord.customer_id = cust.id;

-- ✅ good: every column prefixed with its table alias, no ambiguity
select
    ord.id,
    ord.created_at,
    ord.total_amount,
    cust.name,
    cust.region,
from orders as ord
inner join customers as cust on ord.customer_id = cust.id;
```

### QUALIFY over ROW_NUMBER Subquery

```sql
-- ❌ bad: row_number() wrapped in CTE + filter — verbose, two-pass feel
with ranked_orders as (
    select
        ord.id,
        ord.customer_id,
        ord.created_at,
        ord.total_amount,
        row_number() over (partition by ord.customer_id order by ord.created_at desc) as rn,
    from orders as ord
)
select
    ranked.id,
    ranked.customer_id,
    ranked.created_at,
    ranked.total_amount,
from ranked_orders as ranked
where ranked.rn = 1;

-- ✅ good: qualify — inline window filter, no wrapper CTE needed
-- (Databricks SQL, DuckDB, BigQuery, Snowflake, Spark SQL 3.4+)
select
    ord.id,
    ord.customer_id,
    ord.created_at,
    ord.total_amount,
from orders as ord
qualify row_number() over (partition by ord.customer_id order by ord.created_at desc) = 1;

-- qualify also works with rank(), dense_rank(), etc.
select
    prod.id,
    prod.category_id,
    prod.name,
    prod.price,
from products as prod
qualify rank() over (partition by prod.category_id order by prod.price asc) <= 3;
```

### WHERE Clause / Collation Optimization

```sql
-- ❌ bad: function on column breaks index usage
select ord.id, ord.customer_email, ord.total_amount
from orders as ord
where upper(ord.customer_email) = 'JOHN@EXAMPLE.COM';

-- ✅ good (generic): store/query in consistent casing
select ord.id, ord.customer_email, ord.total_amount
from orders as ord
where ord.customer_email = 'john@example.com';
-- consider: create index idx_orders_email on orders(lower(customer_email));

-- ✅ good (Databricks/Spark SQL): collation — no lower() needed, enables Delta file-skipping
-- step 1: one-time schema change
alter table orders alter column customer_email type string collate utf8_lcase;
-- step 2: refresh statistics for file pruning
analyze table orders compute statistics for columns customer_email;
-- step 3: plain equality — up to 22x faster than lower() wrapper
select ord.id, ord.customer_email, ord.total_amount
from orders as ord
where ord.customer_email = 'john@example.com';

-- collation codes: utf8_lcase (en), de, fr, el_ai, fr_ai, …
-- list all: select * from collations()
-- ga since Databricks Runtime 17.3; preview from DBR 13.3+
```

### OR vs UNION ALL

```sql
-- ❌ bad: or condition — optimizer may not use per-branch indexes
select prod.id, prod.name, prod.category, prod.price
from products as prod
where (prod.category = 'electronics' and prod.price < 1000)
    or (prod.category = 'books' and prod.price < 50);

-- ✅ good: union all with CTEs — each branch uses its own index seek
with electronics as (
    select prod.id, prod.name, prod.category, prod.price
    from products as prod
    where prod.category = 'electronics'
        and prod.price < 1000
),
books as (
    select prod.id, prod.name, prod.category, prod.price
    from products as prod
    where prod.category = 'books'
        and prod.price < 50
)
select electronics.id, electronics.name, electronics.category, electronics.price
from electronics
union all
select books.id, books.name, books.category, books.price
from books;
```

---

## 📈 Database-Agnostic Optimization

### Batch Operations

```sql
-- ❌ bad: row-by-row inserts — N round-trips
insert into products (name, price) values ('Product 1', 10.00);
insert into products (name, price) values ('Product 2', 15.00);
insert into products (name, price) values ('Product 3', 20.00);

-- ✅ good: single batch insert
insert into products (name, price)
values
    ('Product 1', 10.00),
    ('Product 2', 15.00),
    ('Product 3', 20.00);
```

### CTE over Temporary Tables

```sql
-- ❌ bad: temporary table — DDL side-effect, can't be inlined
create temporary table temp_customer_totals as
select
    ord.customer_id,
    sum(ord.total_amount) as total_spent,
    count(*) as order_count,
from orders as ord
where ord.created_at >= '2024-01-01'
group by ord.customer_id;

select cust.name, totals.total_spent, totals.order_count
from temp_customer_totals as totals
join customers as cust on totals.customer_id = cust.id
where totals.total_spent > 1000;

-- ✅ good: CTE — inline, no DDL, readable, group by all
with customer_totals as (
    select
        ord.customer_id,
        sum(ord.total_amount) as total_spent,
        count(*) as order_count,
    from orders as ord
    where ord.created_at >= '2024-01-01'
    group by all
),
high_value_customers as (
    select ct.customer_id, ct.total_spent, ct.order_count
    from customer_totals as ct
    where ct.total_spent > 1000
)
select
    cust.name,
    hvc.total_spent,
    hvc.order_count,
from high_value_customers as hvc
inner join customers as cust on hvc.customer_id = cust.id;
```

---

## ⚡ Databricks / Spark SQL Optimization

### Collations for Case/Accent-Insensitive Comparisons

**Up to 22× faster** than `lower()` wrappers — enables Delta file-skipping and Photon optimization.

```sql
-- ❌ bad: lower() breaks file-skipping, forces full scan
select cust.id, cust.name, cust.email
from customers as cust
where lower(cust.name) = 'john smith';

-- ✅ good: set collation once, use plain equality
alter table customers alter column name type string collate utf8_lcase;
analyze table customers compute statistics for columns name;

select cust.id, cust.name, cust.email
from customers as cust
where cust.name = 'john smith';
```

**Collation reference:**

| Collation                    | Use case                                    |
| ---------------------------- | ------------------------------------------- |
| `utf8_lcase`                 | English case-insensitive (default choice)   |
| `unicode`                    | Unicode-aware, case-sensitive               |
| `de`, `fr`, `el`, `ru`, `zh` | Language-specific ordering                  |
| `<lang>_ai`                  | Accent-insensitive (e.g., `el_ai`, `fr_ai`) |

```sql
-- list all available collations:
select * from collations();

-- set collation at table creation:
create table hero_names (
    greek_name string collate el_ai,
    english_name string collate utf8_lcase
);
```

### QUALIFY for Deduplication / Top-N per Group

```sql
-- latest order per customer — no wrapper CTE needed
select
    ord.id,
    ord.customer_id,
    ord.created_at,
    ord.total_amount,
from orders as ord
qualify row_number() over (partition by ord.customer_id order by ord.created_at desc) = 1;

-- top-3 cheapest products per category
select
    prod.id,
    prod.category_id,
    prod.name,
    prod.price,
from products as prod
qualify rank() over (partition by prod.category_id order by prod.price asc) <= 3;
```

### GROUP BY ALL

```sql
-- clean aggregation without repeating dimension columns
select
    ord.status,
    cust.region,
    cust.segment,
    count(*) as order_count,
    sum(ord.total_amount) as revenue,
    avg(ord.total_amount) as avg_order_value,
from orders as ord
inner join customers as cust on ord.customer_id = cust.id
group by all;
```

### Z-ORDER and Liquid Clustering

```sql
-- z-order: co-locate data for frequently filtered columns
optimize my_table zorder by (customer_id, event_date);

-- liquid clustering (dbr 13.3+): dynamic, no manual maintenance
alter table my_table cluster by (customer_id, event_date);
```

---

## 🛠️ Index Management

### Index Design Principles

```sql
-- ✅ good: covering index — query satisfied from index alone
create index idx_orders_covering
on orders(customer_id, created_at)
include (total_amount, status);  -- sql server syntax
-- other databases: create index idx_orders_covering on orders(customer_id, created_at, total_amount, status);
```

### Partial Index Strategy

```sql
-- ✅ good: partial index — smaller, faster for selective predicates
create index idx_orders_active
on orders(created_at)
where status in ('pending', 'processing');
```

---

## 📊 Performance Monitoring Queries

```sql
-- mysql:
select sl.query_time, sl.lock_time, sl.rows_sent, sl.rows_examined, sl.sql_text
from mysql.slow_log as sl
order by sl.query_time desc;

-- postgresql:
select pss.query, pss.calls, pss.total_time, pss.mean_time
from pg_stat_statements as pss
order by pss.total_time desc;

-- sql server: CTE to avoid inline subexpression
with query_stats as (
    select
        qs.total_elapsed_time / qs.execution_count as avg_elapsed_time,
        qs.execution_count,
        qs.sql_handle,
        qs.statement_start_offset,
        qs.statement_end_offset,
    from sys.dm_exec_query_stats as qs
)
select
    qs.avg_elapsed_time,
    qs.execution_count,
    substring(
        qt.text,
        (qs.statement_start_offset / 2) + 1,
        (
            (case qs.statement_end_offset when -1 then datalength(qt.text) else qs.statement_end_offset end
                - qs.statement_start_offset) / 2
        ) + 1
    ) as query_text,
from query_stats as qs
cross apply sys.dm_exec_sql_text(qs.sql_handle) as qt
order by qs.avg_elapsed_time desc;

-- databricks / spark sql:
explain cost
select ord.customer_id, count(*) as order_count from orders as ord group by all;
```

---

## 🧹 SQL Correctness and Clarity Patterns

### FILTER (WHERE …) over CASE WHEN for Conditional Aggregation

```sql
-- ❌ bad: case when inside aggregate — verbose, harder to read
select
    count(case when ord.status = 'pending' then 1 end) as pending_count,
    count(case when ord.status = 'shipped' then 1 end) as shipped_count,
    sum(case when ord.priority = 'high' then ord.total_amount else 0 end) as high_priority_revenue,
from orders as ord;

-- ✅ good: filter clause — ANSI SQL:2003, clean and composable
select
    count(*) filter (where ord.status = 'pending') as pending_count,
    count(*) filter (where ord.status = 'shipped') as shipped_count,
    sum(ord.total_amount) filter (where ord.priority = 'high') as high_priority_revenue,
from orders as ord;
```

### NOT EXISTS over NOT IN (NULL Safety)

```sql
-- ❌ bad: not in with nullable column — returns zero rows if any value is null!
select ord.id, ord.customer_id, ord.total_amount
from orders as ord
where ord.customer_id not in (select cust.id from customers as cust where cust.status = 'inactive');

-- ✅ good: not exists — safe with nulls, often better plan
select ord.id, ord.customer_id, ord.total_amount
from orders as ord
where not exists (
    select 1
    from customers as cust
    where cust.id = ord.customer_id
        and cust.status = 'inactive'
);

-- ✅ also good: left join anti-pattern (readable, index-friendly)
select ord.id, ord.customer_id, ord.total_amount
from orders as ord
left join customers as cust
    on ord.customer_id = cust.id
    and cust.status = 'inactive'
where cust.id is null;
```

### NULLS LAST / NULLS FIRST in ORDER BY

```sql
-- ❌ bad: null ordering is database-dependent (postgres puts nulls last, sql server first)
select prod.id, prod.name, prod.discontinued_at
from products as prod
order by prod.discontinued_at desc;

-- ✅ good: explicit null ordering — ANSI SQL, portable, predictable
select prod.id, prod.name, prod.discontinued_at
from products as prod
order by prod.discontinued_at desc nulls last;
```

### BETWEEN Gotcha with Timestamps — Use >= / <

```sql
-- ❌ bad: between is inclusive on both ends — misses rows at exact end-of-day boundary
select ord.id, ord.created_at, ord.total_amount
from orders as ord
where ord.created_at between '2024-01-01' and '2024-01-31';
-- e.g. '2024-01-31 12:00:00' is excluded even though it belongs to January

-- ✅ good: half-open interval with >= and < — mathematically correct, portable
select ord.id, ord.created_at, ord.total_amount
from orders as ord
where ord.created_at >= '2024-01-01'
    and ord.created_at < '2024-02-01';
```

### Boolean WHERE Predicate — No Redundant Comparison

```sql
-- ❌ bad: comparing boolean column to true/false literal
select ord.id, ord.customer_id, ord.total_amount
from orders as ord
where ord.is_paid = true
    and ord.is_cancelled = false;

-- ✅ good: use the predicate directly
select ord.id, ord.customer_id, ord.total_amount
from orders as ord
where ord.is_paid
    and not ord.is_cancelled;
```

### Boolean Expression as Alias — No CASE WHEN

```sql
-- ❌ bad: case when just to produce a boolean — redundant and noisy
select
    ord.id,
    ord.total_amount,
    case when ord.total_amount > 1000 then true else false end as is_high_value,
    case when ord.status = 'shipped' then true else false end as is_shipped,
from orders as ord;

-- ✅ good: use the predicate expression directly as the column value
select
    ord.id,
    ord.total_amount,
    (ord.total_amount > 1000) as is_high_value,
    (ord.status = 'shipped') as is_shipped,
from orders as ord;
```

### EXISTS over COUNT(\*) for Existence Checks

```sql
-- ❌ bad: count(*) > 0 — scans all matching rows unnecessarily
select cust.id, cust.name
from customers as cust
where (
    select count(*) from orders as ord where ord.customer_id = cust.id
) > 0;

-- ✅ good: exists — stops at the first matching row
select cust.id, cust.name
from customers as cust
where exists (
    select 1 from orders as ord where ord.customer_id = cust.id
);
```

### Identifier Quoting — Backticks for Names, Single Quotes for Strings

```sql
-- ❌ bad: single quotes used for an identifier — this selects the string literal, not the column!
select 'my name', 'order date'
from events;

-- ❌ bad: unquoted reserved word as column name — syntax error on most databases
select event.order, event.group
from events as event;

-- ✅ good: backticks for identifiers with spaces or reserved words (Databricks/Spark SQL, MySQL)
select
    evt.`my name`,
    evt.`order`,
    evt.`group`,
from events as evt;

-- ✅ good: double quotes for identifiers (ANSI SQL standard — PostgreSQL, SQL Server, DuckDB)
select
    evt."my name",
    evt."order",
    evt."group",
from events as evt;

-- single quotes are for string literals only:
select cust.id, cust.name
from customers as cust
where cust.status = 'active'
    and cust.region = 'EMEA';
```

---

### Query Structure

- [ ] No `select *` — explicit column list with table alias prefix (`ord.id`, `cust.name`)
- [ ] Meaningful table aliases (not `a`, `b`, `c`)
- [ ] CTEs (`with … as`) instead of subqueries or derived tables
- [ ] `qualify` instead of `row_number()` CTE wrappers (where supported)
- [ ] `group by all` for clean aggregations (where supported)
- [ ] Filters pushed as early as possible (inside CTEs when helpful)
- [ ] No functions wrapping indexed columns in `where` clauses
- [ ] `filter (where …)` instead of `count(case when … end)` for conditional aggregation
- [ ] `not exists` / left-join anti-pattern instead of `not in` (NULL safety)
- [ ] `nulls last` / `nulls first` explicit in `order by` when column is nullable
- [ ] `>=` / `<` half-open intervals instead of `between` for timestamp ranges
- [ ] Boolean predicates without redundant `= true` / `= false`
- [ ] Boolean expressions as aliases (`(x = 2) as is_flag`) not `case when x = 2 then true else false end`
- [ ] `exists` instead of `count(*) > 0` for existence checks

### Index Strategy

- [ ] Indexes on frequently filtered/joined columns
- [ ] Composite indexes ordered by selectivity (most selective first)
- [ ] No over-indexing (each index costs on insert/update)
- [ ] Covering indexes for hot read paths
- [ ] Partial indexes for selective predicates

### Data Types and Schema

- [ ] Appropriate data types for storage efficiency
- [ ] Normalized for OLTP, denormalized for OLAP
- [ ] Constraints used to help the query optimizer
- [ ] Large tables partitioned appropriately
- [ ] (Databricks) Collations on string columns with case/accent-insensitive comparisons

### Query Patterns

- [ ] `limit`/`top` for result set control
- [ ] Cursor-based pagination instead of `offset`
- [ ] Batch inserts/updates instead of row-by-row
- [ ] No N+1 queries — use joins or CTEs
- [ ] Prepared statements / parameterized queries for repeated execution

### Performance Testing

- [ ] Tested with realistic data volumes
- [ ] Execution plans reviewed (`explain`, `explain analyze`, `explain cost`)
- [ ] Query performance monitored over time
- [ ] Alerts set for slow queries
- [ ] Index usage analyzed regularly

---

## 📝 Optimization Methodology

1. **Identify**: Use database-specific tools to find slow queries
2. **Analyze**: Examine execution plans — look for full scans, high row counts, missing indexes
3. **Optimize**: CTEs over subqueries · `qualify` over `row_number` wrappers · `group by all` · `filter (where …)` · collations · indexes · boolean clarity
4. **Test**: Verify improvements with realistic data volumes
5. **Monitor**: Continuously track query performance metrics
6. **Iterate**: Regular review and optimization cycle

Focus on measurable improvements. Always test with realistic data volumes and query patterns.
