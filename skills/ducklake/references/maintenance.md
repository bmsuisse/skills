# DuckLake Maintenance

DuckLake never physically deletes data on its own — dropped tables, deleted/updated rows, and
superseded schema versions all stay on disk so time travel keeps working. These functions are how
you reclaim that space and keep read performance healthy. All are called against an attached
DuckLake, e.g. `my_ducklake`.

[Recommended maintenance](https://ducklake.select/docs/stable/duckdb/maintenance/recommended_maintenance) ·
[Expire snapshots](https://ducklake.select/docs/stable/duckdb/maintenance/expire_snapshots) ·
[Cleanup of files](https://ducklake.select/docs/stable/duckdb/maintenance/cleanup_of_files) ·
[Checkpoint](https://ducklake.select/docs/stable/duckdb/maintenance/checkpoint)

## The order that matters

1. **Expire snapshots** — releases old snapshots so their files are no longer "referenced".
2. **Clean up files** — physically deletes files that are no longer referenced by any live snapshot.
3. **Compact** — merges small files and rewrites heavily-deleted-from files for read performance.

Skipping step 1 means step 2 has nothing to delete yet, even for tables you've already dropped.

## Expiring snapshots

```sql
-- by specific snapshot version(s)
CALL ducklake_expire_snapshots('my_ducklake', versions => [2]);

-- by age
CALL ducklake_expire_snapshots('my_ducklake', older_than => now() - INTERVAL '1 week');

-- preview only, no changes made
CALL ducklake_expire_snapshots('my_ducklake', dry_run => true, older_than => now() - INTERVAL '1 week');

-- set a standing retention window instead of calling this manually
CALL my_ducklake.set_option('expire_older_than', '1 month');
```

Snapshot expiration is a **catalog-level** setting only — it can't be scoped to a single schema or
table.

## Cleaning up files

Files aren't deleted the instant they're no longer needed, since a long-running query might still
be scanning them. Instead they land in the `ducklake_files_scheduled_for_deletion` table until
cleanup runs.

```sql
-- files from expired snapshots / merges
CALL ducklake_cleanup_old_files('my_ducklake', older_than => now() - INTERVAL '1 week');
CALL ducklake_cleanup_old_files('my_ducklake', cleanup_all => true);
CALL ducklake_cleanup_old_files('my_ducklake', dry_run => true, older_than => now() - INTERVAL '1 week');

-- untracked/orphaned files left behind by e.g. a crashed writer
CALL ducklake_delete_orphaned_files('my_ducklake', older_than => now() - INTERVAL '1 week');

-- standing option instead of calling cleanup manually
CALL my_ducklake.set_option('delete_older_than', '1 week');
```

It's generally safe to delete files that were scheduled for deletion several days ago, as long as
there are no long-running read transactions still in flight.

## Compaction

```sql
CALL ducklake_merge_adjacent_files('my_ducklake');   -- merge small Parquet files
CALL ducklake_rewrite_data_files('my_ducklake');     -- rewrite files with heavy delete activity
```

Small files pile up when snapshots repeatedly write small batches (and data inlining is off).
Tables with a lot of deletes accumulate delete files that slow down reads until rewritten.

## `CHECKPOINT`

Runs everything above, in order, in one statement:

```sql
CHECKPOINT;
```

Order: `ducklake_flush_inlined_data` → `ducklake_expire_snapshots` → `ducklake_merge_adjacent_files`
→ `ducklake_rewrite_data_files` → `ducklake_cleanup_old_files` → `ducklake_delete_orphaned_files`.

Relevant global options (set via `CALL my_ducklake.set_option(...)`):

| Option | Meaning |
| --- | --- |
| `expire_older_than` | snapshot retention age before expiry |
| `delete_older_than` | age threshold before scheduled-for-deletion files are actually removed |
| `rewrite_delete_threshold` | fraction (0–1) of deleted rows in a file that triggers a rewrite |
| `auto_compact` | whether compaction runs automatically (default `true`) |

For a scheduled/production setup, running `CHECKPOINT` on a cron (daily is a common default) is
usually simpler and safer than calling the individual functions by hand.
