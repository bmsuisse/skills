---
name: data-modeling-dimensional
description: >
  Dimensional data modeling guide for the Fabricks platform — covers the full
  pipeline from staging through raw, transf, core, and semantic layers; fact and
  dimension table design; key strategy; SCD types; bridge tables; degenerate
  dimensions; and config. Use this skill whenever designing or reviewing a new
  fact or dimension table, deciding where logic belongs in the pipeline, choosing
  between SCD1 and SCD2, constructing business keys or surrogate keys, modeling
  many-to-many relationships, or understanding how the staging → bronze → silver →
  gold → semantic layers relate to each other. Trigger on: "design fact table",
  "design dimension", "where does this logic go", "SCD type", "slowly changing
  dimension", "surrogate key", "business key", "grain", "bridge table", "degenerate
  dimension", "layer architecture", "transf vs core", "udf_identity", "udf_key",
  "sentinel", "historized", "__valid_from", "__is_current", "new dim table", "new
  fact table", "data model", "pipeline layer", "bronze", "silver", "gold",
  "semantic layer", "merger", "raw layer", "staging".
---

# Dimensional Data Modeling — Fabricks Platform

This guide describes how dimensional modeling works in Fabricks.Runtime, traced
from the production `sales_order` pipeline. It reflects how the platform actually
works — not generic theory.

---

## Full Pipeline Architecture

Every entity flows forward through six stages. Never build backward dependencies.

```
Source System (SQL Server / ERP)
  ↓
bronze/staging/          ← Extract to ADLS via notebooks (_config.onetrade.yml)
  ↓
silver/raw/              ← Register as Delta tables with CDC metadata
  ↓                        (raw.onetrade_stordh, raw.onetrade_storrh, ...)
gold/transf/             ← Business logic, consolidation, historization
  ├─ scd2/              ← Full history: __valid_from / __valid_to per record
  ├─ merger/             ← Union + enrich multiple raw sources (40+ ref joins)
  ├─ fact/              ← Complex calculations: margins, costs, flags, dates
  └─ dim/               ← Lightweight attribute lookups (current-only)
  ↓
gold/core/               ← Conformed layer — all surrogate keys resolved
  ├─ dim/               ← Final dims: __identity, __key, __is_current
  └─ fact/              ← Final facts: all *_sk FKs, 300+ columns
  ↓
semantic/semantic/       ← BI layer — rename, filter, partition, display UDFs
  ├─ fact/
  └─ dim/
```

---

## What Each Layer Does

### Bronze / Staging
**Purpose:** Extract source data to the data lake.

- Databricks notebooks query source systems (SQL Server, APIs, etc.)
- Config-driven: one `_config.<source>.yml` per source system, one entry per source table
- Output: Delta files in Azure Data Lake — no SQL table definitions at this stage
- Column names at this stage are raw/abbreviated as they come from the source

### Silver / Raw
**Purpose:** Register extracted Delta files as queryable tables with CDC metadata.

- Config-driven registration — no `CREATE TABLE` SQL written by hand
- Mode: `change_data_capture: scd1` (register current state, track changes)
- Every raw table gains framework metadata columns:

```
__valid_from    -- when this version became active
__valid_to      -- when this version was superseded
__is_current    -- true for the active row
__is_deleted    -- soft delete from source CDC
__key           -- source business key
```

Source column names are raw/abbreviated (e.g., `ordnr`, `kltnr`, `artnr`, `vrmant`).
No renaming or business logic at this layer.

### Gold / Transf / SCD2
**Purpose:** Capture full attribute history for slowly changing entities.

- Joins header + line tables using temporal validity windows
- Produces one row per version of a record (not one row per current record)
- Adds `__operation` (`upsert`/`delete`) and preserves `__valid_from`/`__valid_to`
- Output: `transf.scd2_<entity>` tables
- Used as input to `merger/` — not consumed directly by `core/`

### Gold / Transf / Merger
**Purpose:** Consolidate multiple raw sources, rename columns, enrich with reference data.

This is where source abbreviations become business names (`ordnr` → `order_id`).

- `UNION ALL` of all source variants for the same entity
- Adds `__source` column to identify origin (e.g., `"sws"`, `"onprem"`, `"calenso"`)
- Joins to 40+ reference tables to add derived attributes:
  - article master → `product_group_l1_id`, `brand_id`, `supplier_id`
  - customer master → `customer_to_bill_id`, `cluster_id`
  - business unit mapping → `business_unit_id`
- Adds derived flags: `is_transport`, `is_special_order`, `is_direct_order`
- Output: `transf.merger_<entity>` (~190 columns for sales_order)

**No surrogate keys yet.** Business IDs only.

### Gold / Transf / Fact
**Purpose:** All complex business calculations. The heaviest layer.

- Multi-CTE pipeline (450+ lines for sales_order)
- Typical CTEs: stock transfer correction → liquidation flags → date corrections →
  account assignment → cost calculations → margin → due date logic → bonus/IVP
- Adds measures that require cross-joining multiple reference tables:
  - `account_profit_id`, `account_loss_id` (depends on order_type + article class)
  - `standard_cost`, `margin` (supplier price lookup)
  - `due_date`, `overdue_days`, `is_due_date_compliant` (working-day calendar logic)
  - `is_order_backlog`, `is_order_invoiced` (status-code logic)
- Output: `transf.fact_<entity>` (~170 columns)

**Still no surrogate keys.** All joins use business IDs.

### Gold / Transf / Dim
**Purpose:** Lightweight current-state lookups that don't need full history.

- Simple deduplication + attribute selection
- Uses `QUALIFY row_number() over (...) = 1` to get one row per key
- Output: small dimension tables used by `core/fact/` for enrichment

### Gold / Core / Dim
**Purpose:** Final conformed dimensions with stable surrogate keys.

- Adds `__identity` (surrogate key) via `udf_identity_v2()`
- Adds `__key` (composite business key string)
- SCD2 tables split into `dim_<entity>` (current-only) and `dim_<entity>_hist` (all versions)
- `__is_current = true` on current row; historical rows accessible via `_hist` table

### Gold / Core / Fact
**Purpose:** Resolve all business keys to surrogate keys. Final analytical table.

- Joins `transf.fact_<entity>` to all dimension tables
- Converts every `*_id` → `*_sk` using `udf_identity_v2()`
- Adds temporal joins for SCD2 dimensions (join on ID + date range)
- Adds any remaining aggregates that require cross-row logic (e.g., `days_to_status_change`)
- Validated by `min_rows:` check in config
- Output: `core.fact_<entity>` (300+ columns for sales_order)

### Semantic / Semantic
**Purpose:** BI-facing presentation layer only. Zero business logic.

- Filters to relevant records (e.g., invoiced orders only, last 5 years or backlog)
- Renames columns to display names (with backtick-quoted spaces: `` `Order Nr` ``)
- Applies display UDFs: `udf_combi_field()`, `udf_partition_from_date_sk_v2()`
- Conditionally nulls keys that don't apply: `if(is_invoiced, sales_date_sk, null)`
- Declares partitioning: `partition_by: [partition_year, _partition_v2]`
- Declares `parents:` dependencies in config for correct build order

---

## Rule of Thumb: Where Does This Logic Belong?

| What you're doing | Layer |
|---|---|
| Source extraction config | `bronze/staging/` |
| Registering a new source table | `silver/raw/` config |
| Track full attribute history | `gold/transf/scd2/` |
| Union multiple source variants | `gold/transf/merger/` |
| Rename source columns to business names | `gold/transf/merger/` |
| Enrich with reference/lookup data | `gold/transf/merger/` (if simple) or `gold/transf/fact/` (if complex) |
| Calculate margins, costs, dates, status flags | `gold/transf/fact/` |
| Lightweight current-state lookup | `gold/transf/dim/` |
| Resolve surrogate keys | `gold/core/fact/` |
| Join to conformed dimensions | `gold/core/fact/` |
| Conformed dim with surrogate key | `gold/core/dim/` |
| Column renames, BI filters, partitioning | `semantic/semantic/` |

Put logic in the **earliest layer where all required data is available**. If you
find yourself adding a join in `core/` that isn't for key resolution, it probably
belongs in `transf/fact/`.

---

## Key Strategy

Three key types exist for every dimension entity. Understand all three before building.

### 1. Business Key (`_key` in dim, `_bk` in fact)

The natural identifier from the source system. Built using `udf_key()` when composite.

```sql
-- Simple: single source field
cu.no_ as __key                          -- in transf/scd2/customer.sql

-- Composite: multiple fields joined with * separator, nulls become -1
udf_key(array(
    fact.article_id::string,
    fact.row_type_id::string
)) as article_key                        -- in core/fact/sales_order.sql
```

- Stored on the fact table as `<dim>_bk` for debugging (e.g., `item_bk`, `customer_bk`)
- If the business key is a concatenation of multiple source fields, keep it denormalized on the fact — don't collapse it
- Business keys in dimensions are named `_key` (e.g., `item_key`, `cost_center_key`)

### 2. Surrogate Key (`_sk` / `__identity`)

The numeric foreign key used for joins and aggregation. Generated by `udf_identity_v2()`.

```sql
udf_identity_v2(fact.article_key, 'article') as article_sk
udf_identity_v2(fact.customer_id, 'customer') as customer_sk
```

`udf_identity_v2(key, table_name)` dispatches differently per entity — some use
numeric offset ranges, others hash, others have special logic (dates, clusters).
**Never compute surrogates manually** — always use the UDF so the range strategy
is consistent.

**Surrogate key ranges (deliberate, not random):**

| Entity | Range | Strategy |
|---|---|---|
| `customer` | 1–150,000 | `udf_identity_numeric(key, 150000)` |
| `article` | 1–4,390,000 | `udf_identity_numeric(key, 4390000)` |
| `date` | YYYYMMDD format | `date_format(key, "yyyyMMdd")` |
| `time` | HHmm format | `date_format(key, "HHmm")` |
| Default | xxhash64 | `xxhash64(key)` |

Ranges are deliberate — they let you infer entity type from a surrogate value, which
helps debug cross-table join issues.

### 3. Historized Surrogate Key (`_hsk`)

Points to a specific historical version of a SCD2 dimension record. Used when the
fact needs to reflect what the dimension looked like at a point in time.

```sql
udf_identity_v2(deh.__identity, 'employee_hist') as employee_hist_sk
```

Use `_hsk` (not `_sk`) as the suffix when the join is temporal. This makes it clear
that the FK points into a historized table, not the current-state view.

### Sentinel Values

| Value | Meaning |
|---|---|
| `-1` | Business key was NULL in the source — unknown/unmatched dimension member |
| `-2` | Surrogate key join failed — dimension record does not exist yet |
| Special positive value | Hardcoded for specific business cases (e.g., `business_unit_sk = 5` for transport orders) |

Use `udf_sentinel(business_key, surrogate_key)` for optional dimension joins:

```sql
udf_sentinel(concat(fact.article_id, fact.location_id), asi.__identity)
    as article_stock_information_sk
```

---

## Fact Table Design

### Grain

Define the grain before writing a single line of SQL. The grain is the lowest level
of detail in the fact — one row represents exactly one thing (e.g., one sales order
line). Every measure and dimension must be consistent with that grain.

### What goes on a fact table

| Column type | Example | Notes |
|---|---|---|
| Surrogate keys | `customer_sk`, `article_sk` | One per dimension — used for joins in BI |
| Historized SK | `employee_hist_sk` | When dimension is SCD2 and temporal accuracy matters |
| Business keys | `customer_bk`, `item_bk` | Keep for debugging alongside surrogate |
| Degenerate dimensions | `row_type_id`, `order_status_id` | Low-cardinality operational codes — no dim table needed |
| Measures | `sales_amount`, `cost_amount` | Additive facts |
| Flags | `is_inter_company`, `is_transfer_order` | Boolean, `is_` prefix |
| Date keys | `sales_date_sk`, `creation_date_sk` | Integer, joins to `dim_date` |

### Surrogate key resolution pattern (in `core/fact/`)

```sql
-- Step 1: carry the business key forward from transf
fact.customer_id,

-- Step 2: build composite key if needed
udf_key(array(fact.article_id::string, fact.row_type_id::string)) as article_key,

-- Step 3: resolve to surrogate
udf_identity_v2(fact.customer_id, 'customer') as customer_sk,
udf_identity_v2(fact.article_key, 'article') as article_sk,

-- Step 4: LEFT JOIN to dim for attributes you need on the fact (rare)
left join core.dim_article da
    on da.id = fact.article_id
    and da.row_type_id = fact.row_type_id
```

All surrogate key resolution happens in `core/fact/`, not in `transf/` or `semantic/`.

### Temporal joins for SCD2 dimensions

When a fact must reflect the dimension state at the time of the transaction:

```sql
left join core.dim_employee_hist deh
    on deh.login = fact.sales_agent_login
    and fact.sales_date between deh.__valid_from and deh.__valid_to
```

---

## Dimension Table Design

### SCD Type 1 — current state only

Use when historical accuracy is not required (e.g., reference data, lookup tables).
Built in `transf/dim/` and `core/dim/`. One row per business key. The `__identity`
is stable across loads.

```sql
-- core/dim/ structure
__key           -- business key string
__identity      -- surrogate key (bigint)
id, name, ...   -- attributes (current values only)
```

### SCD Type 2 — full history

Use when attribute changes must be tracked over time (customers, articles, employees,
pricing). Built in `transf/scd2/`. Every version of a record gets its own row.

```sql
-- transf/scd2/ output structure
__key           -- business key
__identity      -- surrogate for this specific version
__valid_from    -- start of this version's validity (timestamp)
__valid_to      -- end of this version's validity (timestamp)
__is_current    -- true for the active version
__operation     -- 'upsert' or 'delete' (CDC)
__is_deleted    -- soft-delete flag
id, name, ...   -- attributes (values as of this version)
```

**Contiguous date ranges:** Every SCD2 dimension must have no gaps between
`__valid_from` and `__valid_to`. If no data exists yet, create a dummy record
at the known start date to ensure the range is contiguous.

**Semantic layer filter:** Semantic dim views filter to `__is_current = true`
so BI tools see a simple current-state table. The historized table (`dim_*_hist`)
is available separately for temporal analysis.

---

## Bridge Tables (Many-to-Many)

Use a bridge table when an entity has a many-to-many relationship with the fact
(e.g., an article can have multiple suppliers; a sales order line can link to
multiple articles per supplier).

```sql
-- bridge: dim_article_supplier
article_id, supplier_id, __identity, ...attributes

-- on the fact: sentinel handles the "no supplier for this article" case
udf_key(array(fact.article_id::string, fact.location_id::string))
    as article_stock_information_key,
udf_sentinel(concat(fact.article_id, fact.location_id), asi.__identity)
    as article_stock_information_sk,

left join core.dim_article_stock_information asi
    on asi.article_id = fact.article_id
    and asi.location_id = fact.location_id
    and fact.row_type_id = 0   -- bridge only valid for certain row types
```

---

## Degenerate Dimensions

Store low-cardinality operational codes directly on the fact. Do not create a
dimension table for them.

**Use degenerate dimensions when:**
- Small, stable set of values (< ~20)
- Operational metadata, not analytical attribute
- Not useful as a filter or group-by on its own in BI

```sql
-- Good degenerate dimensions on fact_sales_order:
row_type_id        -- 0=regular, 3=service, 4=complement
order_status_id    -- operational status code
sales_group_id     -- code, not a user-facing attribute
```

---

## Config Files

Every layer folder has a `_config.*.yml` that controls job execution. Each layer
uses slightly different options.

```yaml
# gold/transf/merger/_config.merger.yml
- job:
    step: transf
    topic: merger
    item: sales_order
    options:
      mode: complete
    check_options:
      post_run: true

# gold/transf/fact/_config.fact.yml
- job:
    step: transf
    topic: fact
    item: sales_order
    options:
      mode: complete
    tags: [sales_order]
    check_options:
      post_run: true

# gold/core/fact/_config.fact.yml
- job:
    step: core
    topic: fact
    item: sales_order
    options:
      mode: complete
    tags: [sales_order]
    check_options:
      post_run: true
      min_rows: 68818365      # fail if row count drops below this

# semantic/semantic/fact/_config.fact.yml
- job:
    step: semantic
    topic: fact
    item: sales_order
    tags: [sqlai_sales]
    options:
      mode: complete
      parents:
        - core.fact_sales_order_invoiced   # explicit dependency
    check_options:
      post_run: true
      min_rows: 100000
    table_options:
      partition_by:
        - partition_year
        - _partition_v2
```

| Option | Values | When to use |
|---|---|---|
| `mode: complete` | full rebuild every run | Fact tables, most dimensions |
| `mode: update` | incremental merge | Large SCD2 tables with CDC |
| `change_data_capture: scd1` | merge current state | Type 1 dims |
| `change_data_capture: scd2` | insert new versions | Type 2 dims |
| `tags` | list of strings | Dependency ordering across jobs |
| `parents` | list of table names | Explicit upstream dependency declaration |
| `min_rows` | integer | Fail the job if output drops below this count |
| `post_run` | true/false | Run `<item>.post_run.sql` after load |

Post-run SQL (`.post_run.sql`) runs after the main load — use for reconciliation
checks, derived metrics, or index hints.

---

## Metadata Columns

| Column | Type | Meaning |
|---|---|---|
| `__key` | string | Business key (composite with `*` separator) |
| `__identity` | bigint | Surrogate key |
| `__valid_from` | timestamp | Start of record validity (SCD2) |
| `__valid_to` | timestamp | End of record validity (SCD2) |
| `__is_current` | boolean | True for the current/active version (SCD2) |
| `__is_deleted` | boolean | Soft-delete from source CDC |
| `__operation` | string | `upsert` or `delete` (CDC type) |
| `__source` | string | Source system identifier (e.g., `"sws"`, `"onprem"`) |
| `_metadata` | struct | Framework-managed audit metadata — do not overwrite |

---

## Semantic Layer Rules

The semantic layer is purely a presentation layer. It must not contain business logic.

**What the semantic layer does:**
- Renames columns to user-friendly display names (with backticks for spaces)
- Filters rows (e.g., `WHERE is_order_invoiced = true`, exclude inter-company)
- Applies display UDFs: `udf_combi_field(id, name)` → `"Geberit Vertriebs AG (00008465)"`
- Applies partitioning: `udf_partition_from_date_sk_v2(sales_date_sk)`
- Filters SCD2 dims to `__is_current = true`
- Conditionally nulls out keys when they don't apply: `if(is_invoiced, sales_date_sk, null)`

**What the semantic layer does NOT do:**
- Join to other tables
- Calculate measures
- Apply business rules

---

## Common UDFs Reference

| UDF | Purpose | Example |
|---|---|---|
| `udf_key(array<string>)` | Build composite business key, `*` separator, `-1` for nulls | `udf_key(array(article_id::string, row_type_id::string))` |
| `udf_identity_v2(key, table)` | Resolve business key to surrogate | `udf_identity_v2(customer_id, 'customer')` |
| `udf_sentinel(bk, sk)` | Handle nullable dim joins: -1 if bk null, -2 if sk null | `udf_sentinel(fact.location_id, loc.__identity)` |
| `udf_combi_field(id, name)` | Semantic display: `"Name (ID)"` | `udf_combi_field(customer_id, customer_name)` |
| `udf_partition_from_date_sk_v2(date_sk)` | Convert date_sk to partition column | In semantic layer only |
| `udf_time_identity(timestamp)` | Get numeric time key | For time dimension FK |
