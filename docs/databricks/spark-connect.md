---
title: Spark Connect
description: Run PySpark locally against a remote Databricks cluster via Spark Connect.
---

# Spark Connect

**Skill:** `spark-connect` · **Plugin:** `databricks@bmsuisse-skills`

Run PySpark locally while computation happens on the remote Databricks cluster.

## How it works

```
Local machine (your IDE / script)
        │
        │  Spark Connect protocol (gRPC)
        ▼
Databricks Cluster
        ├─ Unity Catalog tables
        ├─ Delta Lake
        └─ MLflow tracking
```

## `get_spark_session()`

Single utility that auto-detects whether it's running locally or on the cluster:

```python
import os

def get_spark_session():
    if os.getenv("DATABRICKS_RUNTIME_VERSION"):
        from pyspark.sql import SparkSession
        return SparkSession.builder.getOrCreate()

    from databricks.connect import DatabricksSession
    builder = DatabricksSession.builder
    if profile := os.getenv("DATABRICKS_PROFILE"):
        builder = builder.profile(profile)
    return builder.getOrCreate()
```

## Version alignment — critical

`databricks-connect` **must match the cluster's DBR major.minor**. Use the bundled helper:

```bash
python skills/spark-connect/scripts/check_spark_env.py
```

It fetches the cluster's DBR version, compares to installed `databricks-connect`, and creates a matching `.venv_spark_17_4/` if mismatched.

```bash
# Manual install
uv add databricks-connect==17.4.*
```

| DBR | Package |
|---|---|
| 17.4 | `databricks-connect==17.4.*` |
| 17.3 | `databricks-connect==17.3.*` |
| 16.4 | `databricks-connect==16.4.*` |

## `.env` setup

```bash
DATABRICKS_PROFILE=my-profile
DATABRICKS_CLUSTER_ID=1234-567890-abc123
```

## SQL over PySpark API

Prefer `spark.sql()` — easier to read, plan, and optimize:

```python
result = spark.sql("""
    SELECT customer_id, SUM(amount) AS total
    FROM my_catalog.my_schema.sales
    WHERE year = 2026
    GROUP BY customer_id
""")
```

## Troubleshooting

| Error | Fix |
|---|---|
| Version mismatch | Run `check_spark_env.py` — creates `.venv_spark_<major>_<minor>/` |
| `Cannot configure default credentials` | Run `databricks auth login --profile <profile>` |
| Cluster terminated | `databricks clusters start --cluster-id <id>` |
| `Failed to connect via Databricks Connect` | Check `.env`: `DATABRICKS_PROFILE`, `DATABRICKS_CLUSTER_ID` |
