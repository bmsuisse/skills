---
name: fabricks-glossary
plugin: fabricks-data
description: Use this skill whenever company-specific jargon, acronyms, or domain terminology is needed to answer correctly.
version: 1.0.0
---

# Company Glossary — Data Warehouse (Databricks)

This skill provides domain vocabulary, entity definitions, and architecture context for the company's data warehouse, built on Databricks using the Fabricks.Runtime framework. Most of this terminology originates from and is primarily used in the context of that data warehouse.

## How to use this skill

Load only the reference file(s) relevant to your current task:

| Topic | Reference file | Load when... |
|-------|----------------|--------------|
| Acronyms & abbreviations | `references/acronyms.md` | An unknown abbreviation appears (SPT, BU, IVP, HEP, etc.) |
| Core business entities | `references/entities.md` | Working with articles, customers, sales agents, or inventory |
| Domain concepts | `references/domain-concepts.md` | Working with commissions, margin bonuses, campaigns, credit risk, or MDM |
| Naming conventions | `references/conventions.md` | Naming or interpreting tables, columns, schemas, or data layers |
| Fabricks framework | `references/fabricks-framework.md` | Working with steps, jobs, modes, CDC, or pipeline configuration |

## Quick reference — most-used facts

- **Table prefixes**: `dim_` dimensions · `fact_` measures · `ref_` lookups · `scd1_/scd2_` history · `merger_` consolidated · `*_agg` aggregated · `*_hist` snapshots
- **Key column suffixes**: `__key` hash key · `__identity` surrogate · `__is_current` SCD2 flag · `__valid_from/to` SCD2 range · `_sk` foreign surrogate · `_pct` percentage
- **Data layers**: `staging` (raw ingest) → `raw` (SCD applied) → `transf`/`core`/`mdm`/`ml` (gold) → `semantic`/`bme` (presentation) → `distribution` (export)
- **Core schemas**: `core` has surrogate keys (`__identity`); `transf` has business logic but no `core` tables; `semantic` uses UPPERCASE column names with spaces for Power BI