---
name: duckdb
description: >
  Guide for working with DuckDB — CLI usage, SQL execution, reading files (CSV, Parquet, JSON, Excel),
  extensions (httpfs, spatial, json, excel, etc.), and the Python duckdb package.
  Use this skill whenever the user is working with DuckDB, whether via CLI, SQL scripts, or Python.
  Trigger on: duckdb queries, reading local/remote files with duckdb, installing duckdb extensions,
  duckdb in Python/pandas, exporting data, or any question about DuckDB behavior or syntax.
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
