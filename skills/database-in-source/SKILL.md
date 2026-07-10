---
name: database-in-source
plugin: coding
description: >
  Conventions for versioning a PostgreSQL schema as plain `.sql` files inside
  a `database/` folder in the application repo, instead of an ORM migration
  framework. Use this skill whenever the user is creating or organising a
  `database/` folder, adding a new table/view/function/type, deciding where a
  one-off migration script goes, naming `.sql` files, or asking how schema
  layers, object types, permissions, and `COMMENT ON` documentation should be
  laid out in source. Triggers on things like "add a new table to database/",
  "where do table definitions live", "database folder structure", "schema
  layer", "migration script", ".prod file", ".init.sql", or "COMMENT ON".
---

# Database-in-source layout

The Postgres schema is versioned as plain `.sql` files under a `database/` folder in the repo — this folder *is* the source of truth for the schema. [postgres-test-setup](../postgres-test-setup/SKILL.md) applies it to a local Docker DB for tests; a human applies the same files to production.

---

## Layer directories

Top-level directories are numbered by apply order and grouped by conceptual layer (dimension/reference data, facts/transactions, user-editable/app data, staging/import, statistics, ...):

```
database/
├── 1_schema.sql          # CREATE SCHEMA statements
├── 0_public/             # shared types/functions usable from any schema
├── 1_dim/                # dimension / reference tables
├── 3_fact/                # fact / transactional tables
├── 3_imp/                # import / staging tables
├── 4_editing/             # user-editable, app-owned tables
├── 5_stat/                # aggregated / statistics tables
├── 100_permissions.sql   # grants — applied last
```

Layer names and count are per-project. The numeric prefix is what fixes apply order across layers (low numbers first) — don't renumber existing layers when adding a new one, pick the next free number or insert with a decimal-free gap.

---

## Object-type subfolders, in apply order

Within a layer directory, group files by object type. All objects across all layer directories are applied in this priority order (cross-file FK dependencies are resolved automatically by the tool that walks the tree):

| Priority | Directory | Object type |
|---|---|---|
| 1 | `schema` | `CREATE SCHEMA` |
| 2 | `types` | Custom types / enums |
| 3 | `tables` | Tables |
| 4 | `scalar_functions` | Scalar functions |
| 5 | `functions` | Functions |
| 6 | `views` | Views |
| 7 | `table_functions` | Table functions |
| 8 | `procedures` | Procedures |
| 100 | `permissions` | Grants |
| 101 | `indexes` | Indexes |

One object per file: `tables/user.sql`, `views/all_edits.sql`, `types/measurement_unit.sql`.

---

## File-naming conventions

| Suffix | Meaning |
|---|---|
| `<name>.sql` | The object's live definition (`CREATE TABLE`, `CREATE OR REPLACE VIEW`, ...) |
| `<name>.test_data.json` | Seed rows for a table — a JSON array of row objects, loaded after the table is created |
| `<name>.init.sql` | One-time setup for an object (e.g. a backfill), run once, kept separate from the reusable definition |
| `<name>.prod.sql` / `.prod` anywhere in the name | Production-only (real permission grants, real user accounts) — skipped by local test/dev tooling |
| `all.sql` | Generated concatenation of the whole tree — not hand-edited, not committed |

---

## Migrations

One-off, non-idempotent changes (rename/drop column, backfill, data fix) go in a `migrations/` (or `_migration_scripts/`) folder — one file per change, named by date:

```
database/migrations/2026-07-10_customer_geocode.sql
```

Rules:

- Skipped by the local test/dev schema runner — it only applies the layer directories above.
- Update the corresponding table/view `.sql` file in the same change so its definition already reflects the new shape — the migration and the source-of-truth file must never drift apart.
- Applied to production manually, once, by a human, after being verified locally.
- Never edited after being applied — a further change gets a new dated file.

---

## `COMMENT ON` — document schema in the object's own file

Add a `COMMENT ON` for every table, and for any column whose purpose isn't obvious from its name and type (flags, status codes, denormalized fields, units). Put it directly in the table's `.sql` file, right after the `CREATE TABLE` — not in a migration, wiki, or README. It lives with the definition it describes and survives `\d+` / `pg_catalog` inspection.

```sql
-- database/1_dim/tables/user.sql
create table dim.user (
    id bigint generated always as identity primary key,
    email text not null,
    is_active boolean not null default true
);

comment on table dim.user is 'End-user accounts; one row per registered person.';
comment on column dim.user.is_active is 'False once a user is soft-deleted; keep for audit trail.';
```

---

## Quick checklist

- [ ] New table/view/function/type gets its own `.sql` file under the right layer + object-type folder
- [ ] Numeric prefixes preserved — new layers get the next free number, existing ones untouched
- [ ] One-off changes go in `migrations/`, dated, never edited after applying
- [ ] The live `.sql` file is updated in the same change as any migration touching that object
- [ ] `.prod` files are production-only and skipped by local tooling
- [ ] Every table (and non-obvious column) has a `COMMENT ON`, placed in the object's own `.sql` file
