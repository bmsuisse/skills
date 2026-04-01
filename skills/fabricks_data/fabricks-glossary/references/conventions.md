# Fabricks DWH — Naming Conventions

## Table Naming

| Pattern | Description | Example |
|---------|-------------|---------|
| `dim_*` | Dimension table | `core.dim_article`, `core.dim_customer` |
| `fact_*` | Fact table with measures | `core.fact_sales_order`, `core.fact_slim_stock` |
| `ref_*` | Reference / lookup table | `transf.ref_product_group` |
| `bridge_*` | Many-to-many relationship | `core.ref_sales_agent_customer` |
| `scd1_*` | Slowly changing dim type 1 | `transf.scd1_article` |
| `scd2_*` | Slowly changing dim type 2 | `transf.scd2_customer` |
| `merger_*` | Consolidated from multiple sources | `transf.merger_bonsai` |
| `*_agg` | Pre-aggregated for performance | `core.fact_sales_order_contribution_agg` |
| `*_hist` | Historical snapshot | `core.fact_document_agg_hist` |

## Key Column Conventions

| Column / Suffix | Meaning |
|-----------------|---------|
| `__key` | Hash-based composite key for uniqueness detection |
| `__identity` | Surrogate key (auto-generated numeric) — only in `core` schema |
| `__is_current` | `true` = current record in SCD2 |
| `__valid_from`, `__valid_to` | Valid date range for SCD2 history |
| `__source` | Origin system indicator |
| `__is_deleted` | Soft-delete flag |
| `__is_inter_company` | Internal/inter-company transaction flag |
| `_sk` | Surrogate key foreign key reference (e.g., `customer_sk`) |
| `_de`, `_fr`, `_it` | Language-specific translation columns |
| `_pct` | Percentage value |
| `is_hep` | High Engagement Program flag |
| `is_own_brand` | Own brand article flag |
| `is_service` | Service article flag |
| `is_one_off` | One-time article (OTA) flag |
| `main_bu` | Primary business unit (leaf node) |

## Data Layer Architecture

| Layer | Schema | Purpose |
|-------|--------|---------|
| Bronze | `staging` | Raw extraction from source systems |
| Silver | `raw` | SCD1/SCD2 applied via config (no custom SQL) |
| Gold | `transf` | Business logic transformations; no `core` tables allowed |
| Gold | `core` | Enterprise facts/dims with surrogate keys (`__identity`) |
| Gold | `mdm` | Master data management; article deduplication |
| Gold | `ml` | Machine learning models |
| Presentation | `semantic` | Power BI layer; UPPERCASE column names, spaces allowed |
| Presentation | `bme` | Parent-company-specific semantic models |
| Distribution | `distribution` | Exports to external systems |

## Rules
- `transf` must not reference `core` tables directly
- `core` is the only schema that uses `__identity` surrogate keys
- `semantic` columns must be UPPERCASE with spaces for Power BI compatibility
