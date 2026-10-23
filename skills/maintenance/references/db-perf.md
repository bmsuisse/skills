# maintenance: db-perf

Slow queries and Postgres health on the real database, found from `pg_stat_statements`, then reproduced and fixed
on a copy of the schema. Read-only on prod; the output is issues and PRs (indexes, rewritten queries) that go
through the normal migration path (`pgdevkit`'s `database/` folder).

Needs a read-only connection to the prod (or test) database; the repo's README says how. `pg_stat_statements`
must be loaded (`shared_preload_libraries`, on Azure allow-listed in the server parameters) and created
(`create extension if not exists pg_stat_statements`). Not there: that is finding number one, issue.

```sql
-- where the time goes overall, then what is slow per call
select calls, round(total_exec_time::numeric) as total_ms, round(mean_exec_time::numeric, 1) as mean_ms,
       round(max_exec_time::numeric) as max_ms, rows, left(query, 200) as query
from pg_stat_statements
where dbid = (select oid from pg_database where datname = current_database())
order by total_exec_time desc limit 20;          -- repeat with: order by mean_exec_time desc where calls > 10

-- tables read by seq scan again and again
select relname, seq_scan, seq_tup_read, idx_scan, n_live_tup
from pg_stat_user_tables where seq_scan > 100 and n_live_tup > 10000 order by seq_tup_read desc limit 20;

-- unused indexes (cost on every write): check the stats age first (pg_stat_database.stats_reset)
select s.relname, s.indexrelname, s.idx_scan, pg_size_pretty(pg_relation_size(s.indexrelid)) as size
from pg_stat_user_indexes s join pg_index i using (indexrelid)
where s.idx_scan = 0 and not i.indisunique and not i.indisprimary order by pg_relation_size(s.indexrelid) desc;

-- dead tuples / autovacuum lagging
select relname, n_dead_tup, n_live_tup, last_autovacuum from pg_stat_user_tables order by n_dead_tup desc limit 10;
```

`pg_stat_statements` is cumulative since its last reset: don't reset it yourself on a shared database, and read
the numbers relative to `stats_since` (PG 14+). The queries are normalized (`$1`); map one back to the code with
the SQL text (`grep` the repo, the `.sql` files under `sql_roots`).

## Per slow query

1. Reproduce on the test DB with realistic data volume: `explain (analyze, buffers)` and read the plan (seq scan
   on a big table, a bad row estimate, a sort spilling to disk, nested loop over many rows). On prod only plain
   `explain`, and never `analyze` on a statement that writes (or wrap it in `begin; ... rollback;`).
2. Fix the cause in order of preference: the query (a join, a function on an indexed column, `select *`,
   N+1 from the app: one query with a join), then an index (partial, covering; check the write cost and that
   none exists yet), then statistics (`analyze`, extended statistics). Not: a bigger server.
3. Re-run the plan and the numbers, put before/after in the PR. For index/DDL changes use the `database/` conventions
   of `pgdevkit`; `sql-optimization` has the general rules.
4. Anything you can't fix now: `bdt issue create --title "..."` with query, calls, mean/total time, plan.
   Search first, no duplicates (`bdt issue search --state all --since-days 0 "<table or endpoint>"`).

Also report the findings that need no code: unused indexes (list, don't drop; the stats may be young), bloat, a
missing extension. Report: top 5 by total and by mean time, what was fixed, what became an issue.
