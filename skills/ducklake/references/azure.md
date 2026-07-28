# DuckLake with Azure Blob Storage / Data Lake Storage

DuckLake's data files can live on Azure Blob Storage or Azure Data Lake Storage (ADLS) Gen2,
via DuckDB's `azure` extension. The catalog (metadata) still lives in DuckDB/SQLite/PostgreSQL —
only the Parquet `DATA_PATH` moves to Azure.

[DuckDB Azure extension docs](https://duckdb.org/docs/stable/core_extensions/azure) ·
[DuckLake storage backends](https://ducklake.select/docs/stable/duckdb/usage/choosing_storage)

## Install

```sql
INSTALL ducklake;
INSTALL azure;
```

## Authenticate

Create a secret once per session/database. Pick whichever fits your environment:

```sql
-- Connection string (simplest for local dev / a storage account key)
CREATE SECRET azure_secret (
    TYPE azure,
    CONNECTION_STRING 'DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net'
);

-- Credential chain (recommended in Azure-hosted environments: picks up managed identity,
-- az CLI login, env vars, etc. via the Azure SDK's DefaultAzureCredential)
CREATE SECRET azure_secret (
    TYPE azure,
    PROVIDER credential_chain,
    ACCOUNT_NAME 'mystorageaccount'
);

-- Service principal (CI/CD, headless jobs)
CREATE SECRET azure_secret (
    TYPE azure,
    PROVIDER service_principal,
    TENANT_ID 'tenant-id',
    CLIENT_ID 'client-id',
    CLIENT_SECRET 'client-secret',
    ACCOUNT_NAME 'mystorageaccount'
);
```

## Attach a DuckLake with data on Azure

```sql
-- ADLS Gen2 (hierarchical namespace) — abfss://<filesystem>/<path>
ATTACH 'ducklake:metadata.ducklake' AS my_ducklake
    (DATA_PATH 'abfss://my-filesystem/ducklake/');

-- Blob Storage (flat namespace) — az://<container>/<path>
ATTACH 'ducklake:metadata.ducklake' AS my_ducklake
    (DATA_PATH 'az://my-container/ducklake/');

USE my_ducklake;
CREATE TABLE events AS FROM read_csv('local_data.csv');
```

If your secret doesn't set `ACCOUNT_NAME`, use the fully-qualified form instead so DuckDB knows
which storage account to hit:

```sql
ATTACH 'ducklake:metadata.ducklake' AS my_ducklake
    (DATA_PATH 'abfss://mystorageaccount.dfs.core.windows.net/my-filesystem/ducklake/');
```

## ADLS Gen2 vs. Blob Storage

Prefer `abfss://` (ADLS Gen2, hierarchical namespace) over `az://` (flat Blob Storage) when you
have a choice — ADLS supports directory-aware globbing, so DuckDB can prune down to matching
paths directly instead of listing every blob and filtering client-side. This matters more as a
DuckLake table's file count grows, since Hive-style partitioning (see the main SKILL.md) produces
one directory tree per partition.

## Catalog on Azure too?

`DATA_PATH` only controls where Parquet data files go — the catalog (DuckDB file, SQLite, or
PostgreSQL) is a separate connection and isn't affected by these secrets. For a fully Azure-hosted
setup, pair this with a managed PostgreSQL instance (e.g. Azure Database for PostgreSQL) as the
catalog and Azure Storage as `DATA_PATH`.
