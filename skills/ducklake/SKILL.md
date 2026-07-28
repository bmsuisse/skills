---
name: ducklake
description: >
  Guide for working with DuckLake — the open lakehouse format and DuckDB extension that pairs a
  SQL catalog (metadata, transactions) with Parquet files on object/file storage. Covers ATTACH
  syntax, choosing a catalog database (DuckDB, SQLite, PostgreSQL), storing data files on Azure
  Blob Storage / Data Lake Storage, time travel and snapshots, partitioning, schema evolution, and
  maintenance (checkpoint, expiring snapshots, file cleanup, compaction). Use this skill whenever
  the user mentions DuckLake, wants a
  "lakehouse" on top of DuckDB/Parquet, needs multiple processes to read/write the same DuckDB
  data concurrently ("multiplayer DuckDB"), or asks about time travel, snapshot expiry, or
  partitioning in a DuckDB-attached database — even if they call it by an ATTACH string like
  `ducklake:...` rather than the name "DuckLake".
---

# DuckLake

[Docs](https://ducklake.select/docs/stable/) · [Specification](https://ducklake.select/docs/stable/specification/introduction) · [GitHub](https://github.com/duckdb/ducklake)

DuckLake is a lakehouse format: Parquet data files on cheap storage (local disk, Azure Blob/Data
Lake Storage, ...) plus
a transactional SQL database (the "catalog") holding all metadata — table/schema definitions,
snapshots, statistics, partition info. Because the catalog is a real database (not just files),
multiple DuckDB processes can concurrently read and write the same lakehouse — this is what the
docs call "multiplayer DuckDB". On top of that it gets time travel, schema evolution, partitioning,
and transactions for free.

Requires DuckDB v1.5.2+. **Not supported**: indexes, primary keys, foreign keys, or constraint
enforcement — those live in the catalog database's own domain, not in DuckLake tables.

## Install & attach

```sql
INSTALL ducklake;
ATTACH 'ducklake:my_ducklake.ducklake' AS my_ducklake;
USE my_ducklake;
```

This creates a DuckDB file holding the DuckLake catalog schema, plus a `my_ducklake.ducklake.files/`
folder where Parquet data lands. Point data files elsewhere with `DATA_PATH` (the directory must
already exist; prefer relative paths for both the catalog file and `DATA_PATH`):

```sql
ATTACH 'ducklake:my_other_ducklake.ducklake' AS my_other_ducklake (DATA_PATH 'some/other/path/');
USE my_other_ducklake;
```

Reattaching an existing DuckLake uses the same `ATTACH` syntax, or open it directly from the CLI:

```bash
duckdb ducklake:my_ducklake.ducklake
```

Detach when done:

```sql
USE memory;
DETACH my_ducklake;
```

Once attached, it behaves like a normal DuckDB schema — `CREATE TABLE`, `INSERT`, `UPDATE`, `DELETE`
all work as usual:

```sql
CREATE TABLE nl_train_stations AS FROM 'https://blobs.duckdb.org/nl_stations.csv';
UPDATE nl_train_stations SET name_long = 'Johan Cruijff ArenA' WHERE code = 'ASB';

-- the underlying Parquet files are queryable directly, too
FROM 'my_ducklake.ducklake.files/**/*.parquet' LIMIT 10;
```

## Choosing a catalog database

The catalog is any SQL-92-ish transactional database with primary key support. Pick it based on
how many clients need concurrent access:

| Catalog | Concurrency | Notes |
| --- | --- | --- |
| DuckDB (default) | single client only | simplest option, good for local/solo use |
| SQLite | multiple **local** clients | single-writer, but handles retries/attach automatically |
| PostgreSQL 12+ | multi-user, remote clients | recommended for shared/production lakehouses |

```sql
-- SQLite catalog
INSTALL sqlite;
ATTACH 'ducklake:sqlite:metadata.sqlite' AS my_ducklake (DATA_PATH 'data_files/');
USE my_ducklake;

-- PostgreSQL catalog
INSTALL postgres;
ATTACH 'ducklake:postgres:dbname=ducklake_catalog host=localhost' AS my_ducklake (DATA_PATH 'data_files/');
USE my_ducklake;
```

## Cloud storage for data files (Azure)

`DATA_PATH` accepts any DuckDB-supported filesystem, so the Parquet data itself can live on Azure
Data Lake Storage / Blob Storage — independently of which catalog database you picked above (needs
the `azure` extension + an azure secret).

```sql
INSTALL azure;
CREATE SECRET azure_secret (TYPE azure, PROVIDER credential_chain, ACCOUNT_NAME 'mystorageaccount');
ATTACH 'ducklake:metadata.ducklake' AS my_ducklake (DATA_PATH 'abfss://my-filesystem/ducklake/');
```

See [`references/azure.md`](references/azure.md) for the full set of Azure authentication options
(connection string, credential chain, service principal), `abfss://` vs. `az://`, and combining it
with a PostgreSQL catalog for a fully Azure-hosted setup.

## Snapshots & time travel

Every write is a **snapshot** — a commit that atomically changes the database state. Nothing is
physically deleted by default (dropped tables, deleted rows, old versions all stick around), which
is what makes time travel possible until snapshots are explicitly expired (see
[Maintenance](#maintenance)).

```sql
-- list all snapshots
FROM my_ducklake.snapshots();          -- snapshot_id, snapshot_time, schema_version, changes, author, commit_message, ...
FROM my_ducklake.current_snapshot();
FROM my_ducklake.last_committed_snapshot();

-- query a table as of a version or timestamp
SELECT * FROM tbl AT (VERSION => 3);
SELECT * FROM tbl AT (TIMESTAMP => now() - INTERVAL '1 week');

-- attach the whole database pinned to a point in time
ATTACH 'ducklake:metadata.duckdb' (SNAPSHOT_VERSION 3);
ATTACH 'ducklake:metadata.duckdb' (SNAPSHOT_TIME '2025-05-26 00:00:00');
```

Attach author/message metadata to a snapshot from inside its transaction:

```sql
BEGIN;
INSERT INTO my_ducklake.people VALUES (1, 'pedro');
CALL my_ducklake.set_commit_message('Author', 'Message text', extra_info => '{"key": "value"}');
COMMIT;
```

## Partitioning

```sql
ALTER TABLE tbl SET PARTITIONED BY (part_key);
ALTER TABLE tbl SET PARTITIONED BY (year(ts), month(ts));   -- transforms compose
ALTER TABLE tbl RESET PARTITIONED BY;
```

Transforms: `col_name` (identity), `bucket(N, col_name)`, `year(ts)`, `month(ts)`, `day(ts)`, `hour(ts)`.

- Changing the partitioning only affects **newly written** data — existing files keep their old
  layout, and DuckLake tracks per-file partition values in the catalog rather than relying on the
  file paths themselves.
- Files are laid out with Hive partitioning by default (toggle-able globally or per schema/table).
- Partition schemes can evolve over time as requirements change.

## Schema evolution

Schema changes are metadata-only — no data files are rewritten:

```sql
-- add / drop columns (including nested struct fields via dotted path)
ALTER TABLE tbl ADD COLUMN new_column INTEGER;
ALTER TABLE tbl ADD COLUMN new_column VARCHAR DEFAULT 'my_default';
ALTER TABLE tbl ADD COLUMN nested_column.new_field INTEGER;
ALTER TABLE tbl DROP COLUMN new_column;
ALTER TABLE tbl DROP COLUMN nested_column.new_field;

-- rename columns / struct fields / the table itself
ALTER TABLE tbl RENAME new_column TO new_name;
ALTER TABLE tbl RENAME nested_column.new_field TO new_name;
ALTER TABLE tbl RENAME TO tbl_new_name;

-- widen a column type (lossless promotions only, e.g. int32 -> int64, float32 -> float64)
ALTER TABLE tbl ALTER col1 SET TYPE BIGINT;
```

Old snapshots remain readable after a schema change: DuckLake tracks columns by an internal
`column_id`, not by name/position, so it can reconstruct the schema as it looked at any given
snapshot.

## Maintenance

DuckLake keeps everything (old snapshots, superseded files) until you tell it to clean up. Run
`CHECKPOINT;` for the common case — it runs all of the maintenance functions below in order:
`ducklake_flush_inlined_data` → `ducklake_expire_snapshots` → `ducklake_merge_adjacent_files` →
`ducklake_rewrite_data_files` → `ducklake_cleanup_old_files` → `ducklake_delete_orphaned_files`.

```sql
CHECKPOINT;
```

For fine-grained control (e.g. a specific retention policy, or a dry run before deleting anything),
call the individual functions — see [`references/maintenance.md`](references/maintenance.md) for
full parameter details on:

- **Expiring snapshots** (`ducklake_expire_snapshots`) — required before any data can be physically removed
- **Cleaning up files** (`ducklake_cleanup_old_files`, `ducklake_delete_orphaned_files`)
- **Compaction** (`ducklake_merge_adjacent_files`, `ducklake_rewrite_data_files`) — merging small
  Parquet files and rewriting heavily-deleted-from files
- Global options (`expire_older_than`, `delete_older_than`, `rewrite_delete_threshold`, `auto_compact`)

## Ecosystem

DuckLake tables can also be read by DataFusion, Spark, Trino, and PostgreSQL clients, and there's a
preview hosted option via MotherDuck. The format itself (catalog tables + Parquet layout) is
specified independently of the DuckDB extension — see the
[specification docs](https://ducklake.select/docs/stable/specification/introduction) if you need to
inspect or generate the catalog tables (`ducklake_snapshot`, `ducklake_table`, `ducklake_data_file`,
etc.) directly rather than through the extension's SQL functions.
