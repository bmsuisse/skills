---
name: spark-connect
description: >
  Guide for running PySpark code locally against a remote Databricks cluster via
  Spark Connect (databricks-connect). Use this skill when asked how to set up
  Databricks Connect, connect to a cluster from a local machine, run notebooks or
  scripts locally with Spark semantics, understand the get_spark_session() pattern,
  configure .env for Spark Connect, manage the local-vs-cluster execution model, or
  use the autoresearch loop with Databricks. Trigger on: "connect to Databricks
  locally", "databricks-connect setup", "spark connect", "get_spark_session",
  "run notebook locally against cluster", "local Spark", "databricks connect config",
  "DATABRICKS_CLUSTER_ID", "DATABRICKS_PROFILE env".
compatibility: Requires databricks-connect matching the target cluster's DBR version.
---

# Spark Connect — Local Execution Against a Databricks Cluster

**Databricks Connect** (built on Apache Spark Connect) lets you run PySpark code
locally while the actual computation happens on the remote Databricks cluster.

Benefits:
- Local IDE/Jupyter development with full Spark semantics
- No need to upload notebooks manually — scripts run in-place from your machine
- Enables autonomous loops (autoresearch, CI) that submit Spark jobs per iteration

## How It Works

```
Local Machine (your IDE / script)
        │
        │  Spark Connect protocol (gRPC)
        ▼
Databricks Cluster (<DATABRICKS_CLUSTER_ID>)
        │
        ├─ Unity Catalog tables
        ├─ Delta Lake / Feature Store
        └─ MLflow tracking
```

When you call `spark.sql(...)` locally, the query plan is serialized and sent to the
cluster for execution. Results stream back to the local process.

---

## Entry Point — `get_spark_session()`

The recommended pattern is a single utility that auto-detects the environment:

```python
# utils/databricks.py (or equivalent)
import os

def get_spark_session():
    if os.getenv("DATABRICKS_RUNTIME_VERSION"):
        # Running on the cluster natively
        from pyspark.sql import SparkSession
        return SparkSession.builder.getOrCreate()

    # Running locally — use Spark Connect
    from databricks.connect import DatabricksSession
    builder = DatabricksSession.builder
    if profile := os.getenv("DATABRICKS_PROFILE"):
        builder = builder.profile(profile)
    return builder.getOrCreate()
```

Usage in any notebook or script:

```python
from utils.databricks import get_spark_session

spark = get_spark_session()
df = spark.sql("SELECT * FROM my_catalog.my_schema.my_table LIMIT 10")
df.show()
```

| Environment | What happens |
|:---|:---|
| On Databricks cluster | Returns native `SparkSession` |
| Local (Databricks Connect) | Returns `DatabricksSession` via profile/cluster config |

---

## Configuration

### `.env` file (recommended for local dev)

```bash
# .env
DATABRICKS_PROFILE=<your-profile>       # profile name from ~/.databrickscfg
DATABRICKS_CLUSTER_ID=<your-cluster-id> # target all-purpose cluster ID
```

Load it before importing Spark:

```python
from dotenv import load_dotenv
load_dotenv()
from utils.databricks import get_spark_session
spark = get_spark_session()
```

### `~/.databrickscfg` profile

```ini
[your-profile]
host  = https://<workspace>.azuredatabricks.net
token = dapi...
```

Set `DATABRICKS_PROFILE=<your-profile>` and Databricks Connect picks it up.

To create or refresh a profile:

```bash
databricks auth login --profile <your-profile>
```

### Finding cluster info via CLI

Use the **databricks-cli** skill to look up the values you need before filling in `.env`.

```bash
# List all clusters and pick the right one
databricks clusters list --profile <your-profile>

# Get a cluster's DBR version (needed to pin databricks-connect)
databricks clusters get --cluster-id <your-cluster-id> --profile <your-profile> \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d['spark_version'])"

# Start a cluster if it's terminated
databricks clusters start --cluster-id <your-cluster-id> --profile <your-profile>

# List configured auth profiles
databricks auth profiles
```

Once you have the profile name and cluster ID, drop them into `.env`:

```bash
DATABRICKS_PROFILE=<value from `databricks auth profiles`>
DATABRICKS_CLUSTER_ID=<value from `databricks clusters list`>
```

See the **databricks-cli** skill for full CLI reference and auth setup.

---

### Installing the dependency


```bash
uv add databricks-connect==<dbr-version>.*
```

The version **must match the Databricks Runtime (DBR)** of the target cluster.

| DBR version | Package |
|:---|:---|
| 17.3 | `databricks-connect==17.3.*` |
| 16.4 | `databricks-connect==16.4.*` |
| 15.4 | `databricks-connect==15.4.*` |

Find the cluster's DBR version:

```bash
databricks clusters get --cluster-id <your-cluster-id> --profile <your-profile> \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d['spark_version'])"
```

---

## Preferred Pattern — SQL over PySpark API

Prefer `spark.sql()` for data queries; it's easier to read, plan, and optimize:

```python
# Preferred
result = spark.sql("""
    SELECT customer_id, SUM(amount) AS total
    FROM my_catalog.my_schema.sales
    WHERE year = 2026
    GROUP BY customer_id
""")

# Avoid unless UDFs or ML pipelines require it
result = df.filter(F.col("year") == 2026).groupBy("customer_id").agg(...)
```

---

## On-Cluster Package Management

When a script runs **on** the cluster (not locally), auto-install dependencies from
`pyproject.toml` on first import so the cluster matches the local environment:

```python
def _auto_install_packages():
    if os.getenv("DATABRICKS_RUNTIME_VERSION"):
        install_packages_from_pyproject(restart_python=False)
```

This avoids manual cluster library configuration.

---

## Autoresearch Loop — Execution Model

The `autoresearch` skill's experiment loop works naturally with Spark Connect:

```
Local machine (autoresearch loop)
  └─ edits notebook / script
  └─ commits the change
  └─ runs: uv run python notebooks/my_script.py
            └─ get_spark_session()  →  Spark Connect  →  Databricks Cluster
            └─ reads metric from stdout / MLflow
  └─ keep or revert based on metric
  └─ next iteration
```

**Spark-specific considerations for autoresearch:**

- Cluster cold starts add ~1–2 min — account for this in the baseline measurement
- Use `hyperfine --warmup 1` (not 3+) to avoid unnecessary cluster compute cost
- Set the time budget cap generously: `2× baseline` is safe for remote runs
- Read the **autoresearch** skill for the full loop protocol

---

## Troubleshooting

| Error | Fix |
|:---|:---|
| `databricks-connect not installed` | `uv add databricks-connect==<dbr>.*` |
| `Failed to connect via Databricks Connect` | Check `.env`: `DATABRICKS_PROFILE`, `DATABRICKS_CLUSTER_ID` |
| `Cannot configure default credentials` | Run `databricks auth login --profile <your-profile>` |
| `Cluster not found` | Verify `DATABRICKS_CLUSTER_ID` matches a running cluster |
| Version mismatch | Ensure `databricks-connect` version matches cluster DBR |
| `DATABRICKS_RUNTIME_VERSION` missing locally | Expected — means you're running locally, Connect is used |
| Cluster terminated | Start the cluster manually or via `databricks clusters start --cluster-id <id>` |
