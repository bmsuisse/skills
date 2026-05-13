# Temporal Tables (row-level history)

Use [nearform/temporal_tables](https://github.com/nearform/temporal_tables) — a pure PL/pgSQL trigger that archives every changed row to a parallel history table. Copy `versioning_function.sql` and `system_time_function.sql` from the repo into `db/migrations/` and apply them as a baseline migration.

For each versioned table, add `sys_period`, create the history table with `LIKE`, and attach the trigger:

```sql
alter table users
    add column sys_period tstzrange not null default tstzrange(current_timestamp, null);

create table users_history (like users);

create index on users_history using gist (id, sys_period);

create trigger users_versioning
before insert or update or delete on users
for each row execute procedure versioning(
    'sys_period',    -- system-period column
    'users_history', -- history table name
    true,            -- conflict mitigation
    false             -- skip entry when no values changed
);
```

`CREATE TABLE … LIKE` copies all columns and their types. Do not add a PK to the history table — the same `id` appears once per version.

Query point-in-time with `@>`:

```sql
select * from users_history where id = %(id)s and sys_period @> %(as_of)s::timestamptz
```

`set_system_time('2023-01-01+00')` / `set_system_time(null)` backdates operations (useful for migrations).
