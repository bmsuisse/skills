# Fabricks Framework — Core Concepts

Fabricks is a SQL-first, YAML-orchestrated framework for Databricks Lakehouse pipelines.

## Layers

| Layer | Step name | Purpose |
|-------|-----------|---------|
| Bronze | `staging` | Land raw data as-is; no business logic |
| Silver | `raw` | Standardise, clean, deduplicate; apply CDC (SCD1/SCD2) |
| Gold | `transf`, `core`, `mdm`, `ml` | Business logic, dimensional models, marts |
| Presentation | `semantic`, `bme` | Power BI / consumption layer |
| Distribution | `distribution` | Export to external systems |

## Key Concepts

- **Step**: Layer type (Bronze / Silver / Gold) — defines defaults and behaviour
- **Job**: Concrete work unit identified by `topic` + `item`; belongs to a step
- **Mode**: Write strategy — e.g., `append`, `update`, `complete`, `memory`
- **CDC**: Change Data Capture — `nocdc`, `scd1` (current state), `scd2` (full history)
- **Extender**: Python transform applied to a DataFrame before writing
- **UDF**: Custom SQL function registered on the Spark session
- **Parser**: Custom source reader (e.g., parquet, csv, json, or bespoke)

## CDC System Columns

| Column | Meaning |
|--------|---------|
| `__key` | Hash-based business key for CDC merge |
| `__is_current` | True = current active record (SCD1/SCD2) |
| `__is_deleted` | Soft-delete flag (SCD1) |
| `__valid_from`, `__valid_to` | Validity window (SCD2) |
| `__identity` | Auto-incremented surrogate key (Gold/core only) |
| `__source` | Origin system indicator |
