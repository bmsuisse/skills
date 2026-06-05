---
name: duckdb
description: >
  Guide for working with DuckDB — CLI usage, SQL execution, reading files (CSV, Parquet, JSON, Excel),
  extensions (httpfs, spatial, json, excel, postgres, etc.), and the Python duckdb package.
  Use this skill whenever the user is working with DuckDB, whether via CLI, SQL scripts, or Python.
  Trigger on: duckdb queries, reading local/remote files with duckdb, installing duckdb extensions,
  duckdb in Python/pandas, exporting data, attaching or querying PostgreSQL from DuckDB, or any question about DuckDB behavior or syntax.
---

# DuckDB

[Docs](https://duckdb.org/docs/) · [SQL Reference](https://duckdb.org/docs/sql/introduction) · [Python API](https://duckdb.org/docs/api/python/overview)

## CLI

Can be installed via `uv add duckdb-cli>=1.5 --group dev`

```bash
uv run duckdb                        # in-memory session
uv run duckdb mydb.duckdb            # persistent database
uv run duckdb mydb.duckdb -c "SELECT 42"   # run one statement
uv run duckdb mydb.duckdb < script.sql     # run a file
```

Useful dot-commands inside the shell:

| Command                        | Effect                  |
| ------------------------------ | ----------------------- |
| `.tables`                      | list tables             |
| `.schema tablename`            | show DDL                |
| `.mode csv` / `.mode markdown` | output format           |
| `.output file.csv`             | redirect output to file |
| `.timer on`                    | show query timing       |
| `.exit`                        | quit                    |

[CLI docs](https://duckdb.org/docs/api/cli/overview)

---

## Reading Files

DuckDB can query files directly — no import step needed.

```sql
-- CSV
SELECT * FROM read_csv('data.csv');
SELECT * FROM read_csv('data.csv', header=true, delim=';');
SELECT * FROM 'data.csv';          -- auto-detected shorthand

-- Parquet
SELECT * FROM read_parquet('data.parquet');
SELECT * FROM read_parquet('s3://bucket/path/*.parquet');  -- requires httpfs

-- JSON
SELECT * FROM read_json('data.json');
SELECT * FROM read_json_auto('data.json');   -- infers schema

-- Multiple files / glob
SELECT * FROM read_csv('folder/*.csv');
```

[CSV](https://duckdb.org/docs/data/csv/overview) · [Parquet](https://duckdb.org/docs/data/parquet/overview) · [JSON](https://duckdb.org/docs/data/json/overview)

### Exporting

```sql
COPY (SELECT * FROM tbl) TO 'out.parquet' (FORMAT PARQUET);
COPY (SELECT * FROM tbl) TO 'out.csv' (HEADER, DELIMITER ',');
```

---

## Extensions

Install once per database, then load each session (or use `AUTOLOAD`):

```sql
INSTALL httpfs;   LOAD httpfs;
INSTALL spatial; LOAD spatial;
INSTALL excel;   LOAD excel;
INSTALL json;    LOAD json;      -- usually auto-loaded
```

| Extension  | Use case                                      |
| ---------- | --------------------------------------------- |
| `httpfs`   | Read/write S3, GCS, HTTP URLs                 |
| `spatial`  | Geospatial types and functions (PostGIS-like) |
| `excel`    | Read `.xlsx` files via `read_xlsx()`          |
| `json`     | JSON functions (often bundled)                |
| `iceberg`  | Apache Iceberg table support                  |
| `delta`    | Delta Lake support                            |
| `postgres` | Attach and query a Postgres DB                |

```sql
-- S3 example (needs httpfs)
SET s3_region='eu-central-1';
SELECT * FROM read_parquet('s3://my-bucket/data/*.parquet');

-- Attach Postgres
ATTACH 'host=localhost dbname=mydb user=me' AS pg (TYPE POSTGRES);
SELECT * FROM pg.public.orders LIMIT 10;
```

[Extensions list](https://duckdb.org/docs/extensions/overview)

---

## PostgreSQL Extension

[Docs](https://duckdb.org/docs/current/core_extensions/postgres/overview)

Lets DuckDB read and write directly from/to a live PostgreSQL instance. Auto-loaded on first use; to install manually:

```sql
INSTALL postgres;
LOAD postgres;
```

### Connecting

```sql
-- Read-write (localhost, default user/db)
ATTACH '' AS pg (TYPE postgres);

-- Explicit connection string, read-only
ATTACH 'dbname=mydb user=postgres host=127.0.0.1' AS pg (TYPE postgres, READ_ONLY);

-- Attach only one schema
ATTACH 'dbname=mydb user=postgres host=127.0.0.1' AS pg (TYPE postgres, SCHEMA 'public');

-- Disconnect
DETACH pg;
```

Connection string parameters: `host`, `port` (5432), `dbname`, `user`, `password`, `passfile`, `hostaddr`, `connect_timeout`.
URI form also works: `postgresql://username@hostname/dbname`.

You can also configure the connection via **secrets** (see [Secrets page](https://duckdb.org/docs/current/core_extensions/postgres/secrets)) or **environment variables** (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`).

### Reading

Once attached, tables are queried as if they were local DuckDB tables — data is read from Postgres at query time:

```sql
SHOW ALL TABLES;
SELECT * FROM pg.public.orders LIMIT 10;

-- Copy into DuckDB to avoid repeated round-trips
CREATE TABLE local_orders AS FROM pg.public.orders;
```

### Writing

```sql
ATTACH 'dbname=mydb' AS pg (TYPE postgres);

CREATE TABLE pg.tbl (id INTEGER, name VARCHAR);
INSERT INTO pg.tbl VALUES (42, 'DuckDB');
UPDATE pg.tbl SET name = 'Updated' WHERE id = 42;
DELETE FROM pg.tbl WHERE id = 42;
ALTER TABLE pg.tbl ADD COLUMN k INTEGER;
DROP TABLE pg.tbl;

CREATE VIEW pg.v1 AS SELECT 42;
CREATE SCHEMA pg.s1;
DROP SCHEMA pg.s1;
```

### COPY / export

```sql
-- Postgres table -> Parquet
COPY pg.tbl TO 'data.parquet';

-- Parquet -> Postgres table
COPY pg.tbl FROM 'data.parquet';

-- Full database copy into DuckDB
COPY FROM DATABASE pg TO my_duckdb_db;
```

### Transactions

```sql
BEGIN;
INSERT INTO pg.tmp VALUES (42);
ROLLBACK;   -- or COMMIT
```

### Running arbitrary SQL in Postgres

```sql
-- Read query
SELECT * FROM postgres_query('pg', 'SELECT * FROM cars LIMIT 3');

-- DDL / DML (write)
CALL postgres_execute('pg', 'CREATE TABLE my_table (i INTEGER)');
```

### Schema cache

DuckDB caches Postgres schema info. If another connection changes the schema externally, clear the cache:

```sql
CALL pg_clear_cache();
```

For full details on secrets, connection pool tuning, and all functions, see [`references/postgres.md`](references/postgres.md).

### Useful settings

| Setting | Description | Default |
| --- | --- | --- |
| `pg_connection_limit` | Max concurrent PG connections | 64 |
| `pg_use_binary_copy` | Use BINARY protocol for COPY | true |
| `pg_experimental_filter_pushdown` | Push WHERE filters to PG | true |
| `pg_array_as_varchar` | Read PG arrays as VARCHAR | false |
| `pg_use_ctid_scan` | Parallel scan via ctids | true |

```sql
SET pg_connection_limit = 10;
```


---

## Python

```bash
pip install duckdb
```

```python
import duckdb

# In-memory (default)
with duckdb.connect() as con:
    df = con.execute("SELECT * FROM read_csv('data.csv')").df()

# Persistent
with duckdb.connect("mydb.duckdb") as con:
    # Query → DataFrame
    df = con.execute("SELECT * FROM read_csv('data.csv')").df()

    # Register a DataFrame as a table
    import pandas as pd
    df = pd.read_csv("data.csv")
    con.register("df_view", df)
    result = con.execute("SELECT count(*) FROM df_view").fetchall()

    # Parameterized queries
    con.execute("SELECT * FROM tbl WHERE id = ?", [42])

# Query a DataFrame directly (no connection needed)
result = duckdb.sql("SELECT * FROM df WHERE value > 10").df()
```

[Python API docs](https://duckdb.org/docs/api/python/overview)

---

## Useful SQL Patterns

```sql
-- Describe a file schema without loading it
DESCRIBE SELECT * FROM read_parquet('data.parquet');

-- Summarize a table
SUMMARIZE my_table;

-- Create table from file
CREATE TABLE orders AS SELECT * FROM read_csv('orders.csv');

-- Window functions
SELECT *, row_number() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn
FROM employees;

-- PIVOT
PIVOT sales ON region USING sum(amount);

-- Unnest arrays
SELECT unnest([1, 2, 3]) AS val;
```

[SQL functions](https://duckdb.org/docs/sql/functions/overview) · [Window functions](https://duckdb.org/docs/sql/window_functions)
