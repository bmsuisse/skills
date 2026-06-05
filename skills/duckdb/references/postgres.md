# DuckDB PostgreSQL Extension — Reference

[Overview](https://duckdb.org/docs/current/core_extensions/postgres/overview) · [Secrets](https://duckdb.org/docs/current/core_extensions/postgres/secrets) · [Functions](https://duckdb.org/docs/current/core_extensions/postgres/functions)

## Secrets

Store connection credentials in the Secrets Manager instead of inline in connection strings (inline credentials may appear in error output).

```sql
-- Temporary secret (this session only)
CREATE SECRET (
    TYPE postgres,
    HOST '127.0.0.1',
    PORT 5432,
    DATABASE postgres,
    USER 'postgres',
    PASSWORD 'secret'
);

-- Persistent secret (survives across sessions)
CREATE PERSISTENT SECRET my_pg_secret (
    TYPE postgres,
    HOST '127.0.0.1',
    PORT 5432,
    DATABASE postgres,
    USER 'postgres',
    PASSWORD 'secret'
);
```

Once a secret exists, ATTACH picks it up automatically:

```sql
ATTACH '' AS pg (TYPE postgres);                          -- uses secret
ATTACH 'dbname=other_db' AS pg2 (TYPE postgres);          -- overrides just dbname
ATTACH '' AS pg3 (TYPE postgres, SECRET my_pg_secret);    -- explicit named secret
```

### All secret configuration options

Mirrors libpq connection parameters. Common ones:

| Option | Description |
|---|---|
| `HOST` / `HOSTNAME` | Hostname (alias: `HOSTNAME`) |
| `HOSTADDR` | IP address |
| `PORT` | Port (default 5432) |
| `DBNAME` / `DATABASE` | Database name |
| `USER` / `USERNAME` | Username |
| `PASSWORD` | Password |
| `PASSFILE` | Path to `.pgpass` file |
| `CONNECT_TIMEOUT` | Connection timeout (seconds) |
| `SSLMODE` | SSL mode (`disable`, `require`, `verify-full`, etc.) |
| `SSLCERT` / `SSLKEY` / `SSLROOTCERT` | Client certificate paths |
| `APPLICATION_NAME` | App name shown in pg_stat_activity |
| `URI` | Full connection URI instead of separate options |
| `AWS_RDS_SECRET` | Name of an `rds` secret for IAM auth (see below) |

Full list: `REQUIRE_AUTH`, `CHANNEL_BINDING`, `CLIENT_ENCODING`, `OPTIONS`, `FALLBACK_APPLICATION_NAME`, `KEEPALIVES`, `KEEPALIVES_IDLE/INTERVAL/COUNT`, `TCP_USER_TIMEOUT`, `REPLICATION`, `GSSENCMODE`, `REQUIRESSL`, `SSLNEGOTIATION`, `SSLCOMPRESSION`, `SSLKEYLOGFILE`, `SSLPASSWORD`, `SSLCERTMODE`, `SSLCRL`, `SSLCRLDIR`, `SSLSNI`, `REQUIREPEER`, `SSL_MIN/MAX_PROTOCOL_VERSION`, `KRBSRVNAME`, `GSSLIB`, `GSSDELEGATION`, `SCRAM_CLIENT_KEY`, `SCRAM_SERVER_KEY`, `SERVICE`, `TARGET_SESSION_ATTRS`, `LOAD_BALANCE_HOSTS`, `OAUTH_*`.

### AWS RDS IAM Authentication

```sql
-- Step 1: RDS secret (generates auth token via AWS SDK)
CREATE SECRET aws_rds_secret1 (
    TYPE rds,
    PROVIDER credential_chain,
    CHAIN 'env;sso;',
    REGION 'eu-west-1',
    RDS_USER 'postgres',
    RDS_HOST 'mydb.xxxx.eu-west-1.rds.amazonaws.com',
    RDS_PORT '5432'
);

-- Step 2: Postgres secret references the RDS secret
CREATE SECRET pg_rds_secret1 (
    TYPE postgres,
    HOST 'mydb.xxxx.eu-west-1.rds.amazonaws.com',
    PORT '5432',
    USER 'postgres',
    DATABASE 'postgres',
    SSLMODE require,
    AWS_RDS_SECRET aws_rds_secret1   -- token auto-refreshed every 15 min
);
```

Requires the `aws` extension. Token refresh is handled automatically by the postgres extension.

### Storing secrets in PostgreSQL

```sql
-- Store any DuckDB secret inside an attached Postgres database
ATTACH 'postgres:' AS p1 (
    SECRET pg_rds_secret1,
    SECRET_STORAGE_TABLE duckdb_secrets
);

CREATE OR REPLACE SECRET s3_secret1 IN postgres_p1 (
    TYPE s3,
    PROVIDER credential_chain,
    CHAIN 'env;sso;',
    REGION 'eu-west-1'
);

-- List secrets stored there
FROM duckdb_secrets() WHERE storage = 'postgres_p1';
```

Secrets are stored unencrypted — suitable for non-sensitive secrets (e.g. S3 credentials via credential chain). Pass `SECRET_STORAGE_TABLE=''` to disable.

---

## Connection Pool

Each `ATTACH` creates a connection pool. Configure with `postgres_configure_pool()`.

```sql
-- View pool stats for all attached databases
FROM postgres_configure_pool();

-- Configure a specific pool
FROM postgres_configure_pool(
    catalog_name    = 'pg',
    acquire_mode    = 'wait',      -- 'force' | 'wait' | 'try'
    max_connections = 20,
    wait_timeout_millis = 5000,
    idle_timeout_millis = 60000,
    max_lifetime_millis = 300000,
    enable_reaper_thread = true,
    health_check_query = 'SELECT 1'
);
```

### Pool parameters

| Parameter | Description | Default |
|---|---|---|
| `catalog_name` | Name of attached DB to configure (required when setting anything) | NULL (list all) |
| `acquire_mode` | `force` (always connect), `wait` (block), `try` (fail fast) | `force` |
| `max_connections` | Max cached connections (can be temporarily exceeded by parallel scans) | — |
| `wait_timeout_millis` | Max wait in `wait` mode | — |
| `idle_timeout_millis` | Max idle time before closing a pooled connection | — |
| `max_lifetime_millis` | Max total lifetime of a connection | — |
| `enable_reaper_thread` | Background thread to enforce idle/lifetime timeouts | false |
| `enable_thread_local_cache` | Pin connections to threads (faster but reduces sharing) | — |
| `health_check_query` | Query run to validate connection health | — |

### Pool statistics (returned columns)

`available_connections`, `cache_hits`, `cache_misses`, `try_failures`, `thread_local_cache_hits/misses`, `reaper_thread_running`, `reaper_thread_period_millis`.

---

## Functions

### `pg_clear_cache()`

Clears cached schema info (table/column lists) for all attached Postgres catalogs. Call after external schema changes.

```sql
CALL pg_clear_cache();
```

### `postgres_query(db, sql [, params, use_transaction])`

Run a read query in an attached Postgres database and return results as a table.

```sql
FROM postgres_query('pg', 'SELECT * FROM orders WHERE id = $1', params=row(42::INTEGER));
```

`use_transaction` (default `TRUE`) — wraps in a transaction if one isn't already open.  
`params` — pass as a `STRUCT` / `row(...)` for parameterized queries (text protocol only).

### `postgres_execute(db, sql [, use_transaction])`

Run DDL or DML in Postgres (no result returned).

```sql
CALL postgres_execute('pg', 'VACUUM ANALYZE orders', use_transaction=FALSE);
CALL postgres_execute('pg', 'CREATE INDEX idx_orders_id ON orders(id)');
```

### `postgres_configure_pool([options])`

See [Connection Pool](#connection-pool) above.

### `read_postgres_binary(file_path [, columns, buffer_size])`

Read a PostgreSQL binary dump file directly.

```sql
-- Write
COPY (SELECT 42::INTEGER AS a, 'foo'::VARCHAR AS b) TO 'dump.bin' (FORMAT postgres_binary);

-- Read back
FROM read_postgres_binary('dump.bin', columns={a: 'INTEGER', b: 'VARCHAR'});
```

`buffer_size` defaults to 32 KB.

### Deprecated functions

These exist but should not be used in new code:

| Function | Replacement |
|---|---|
| `postgres_attach(...)` | `ATTACH ... (TYPE postgres)` |
| `postgres_scan(...)` | Direct SQL on attached DB |
| `postgres_scan_pushdown(...)` | Direct SQL on attached DB |
