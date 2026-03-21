---
name: databricks-cli
description: >
  Databricks CLI operations: auth, profiles, data exploration, bundles, and
  notebook execution. Use this skill for ANY Databricks task — running or
  debugging notebooks on the cluster, executing SQL queries, exploring tables,
  deploying jobs, or fixing notebook errors. Trigger whenever the user mentions
  "run the notebook", "execute on Databricks", "run on the cluster", "fix the
  notebook error", "query the table", or anything involving the Databricks workspace.
compatibility: Requires databricks CLI (>= v0.292.0)
metadata:
  version: "0.2.0"
---

# Databricks

Core skill for Databricks CLI, authentication, and data exploration.

## Product Skills

For specific products, use dedicated skills:
- **databricks-jobs** - Lakeflow Jobs development and deployment
- **databricks-pipelines** - Lakeflow Spark Declarative Pipelines (batch and streaming data pipelines)
- **databricks-apps** - Full-stack TypeScript app development and deployment
- **databricks-lakebase** - Lakebase Postgres Autoscaling project management

## Prerequisites

1. **CLI installed**: Run `databricks --version` to check.
   - **If the CLI is missing or outdated (< v0.292.0): STOP. Do not proceed or work around a missing CLI.**
   - **Read the [CLI Installation](databricks-cli-install.md) reference file and follow the instructions to guide the user through installation.**
   - Note: In sandboxed environments (Cursor IDE, containers), install commands write outside the workspace and may be blocked. Present the install command to the user and ask them to run it in their own terminal.

2. **Authenticated**: `databricks auth profiles`
   - If not: see [CLI Authentication](databricks-cli-auth.md)

## Profile Selection - CRITICAL

**NEVER auto-select a profile.**

1. List profiles: `databricks auth profiles`
2. Present ALL profiles to user with workspace URLs
3. Let user choose (even if only one exists)
4. Offer to create new profile if needed

## Claude Code - IMPORTANT

Each Bash command runs in a **separate shell session**.

```bash
# WORKS: --profile flag
databricks apps list --profile my-workspace

# WORKS: chained with &&
export DATABRICKS_CONFIG_PROFILE=my-workspace && databricks apps list

# DOES NOT WORK: separate commands
export DATABRICKS_CONFIG_PROFILE=my-workspace
databricks apps list  # profile not set!
```

## Data Exploration — Use AI Tools

**Use these instead of manually navigating catalogs/schemas/tables:**

```bash
# discover table structure (columns, types, sample data, stats)
databricks experimental aitools tools discover-schema catalog.schema.table --profile <PROFILE>

# run ad-hoc SQL queries
databricks experimental aitools tools query "SELECT * FROM table LIMIT 10" --profile <PROFILE>

# find the default warehouse
databricks experimental aitools tools get-default-warehouse --profile <PROFILE>
```

See [Data Exploration](data-exploration.md) for details.

## Quick Reference

**⚠️ CRITICAL: Some commands use positional arguments, not flags**

```bash
# current user
databricks current-user me --profile <PROFILE>

# list resources
databricks apps list --profile <PROFILE>
databricks jobs list --profile <PROFILE>
databricks clusters list --profile <PROFILE>
databricks warehouses list --profile <PROFILE>
databricks pipelines list --profile <PROFILE>
databricks serving-endpoints list --profile <PROFILE>

# ⚠️ Unity Catalog — POSITIONAL arguments (NOT flags!)
databricks catalogs list --profile <PROFILE>

# ✅ CORRECT: positional args
databricks schemas list <CATALOG> --profile <PROFILE>
databricks tables list <CATALOG> <SCHEMA> --profile <PROFILE>
databricks tables get <CATALOG>.<SCHEMA>.<TABLE> --profile <PROFILE>

# ❌ WRONG: these flags/commands DON'T EXIST
# databricks schemas list --catalog-name <CATALOG>    ← WILL FAIL
# databricks tables list --catalog <CATALOG>           ← WILL FAIL
# databricks sql-warehouses list                       ← doesn't exist, use `warehouses list`
# databricks execute-statement                         ← doesn't exist, use `experimental aitools tools query`
# databricks sql execute                               ← doesn't exist, use `experimental aitools tools query`

# When in doubt, check help:
# databricks schemas list --help

# get details
databricks apps get <NAME> --profile <PROFILE>
databricks jobs get --job-id <ID> --profile <PROFILE>
databricks clusters get --cluster-id <ID> --profile <PROFILE>

# bundles
databricks bundle init --profile <PROFILE>
databricks bundle validate --profile <PROFILE>
databricks bundle deploy -t <TARGET> --profile <PROFILE>
databricks bundle run <RESOURCE> -t <TARGET> --profile <PROFILE>
```

## Clusters

### Default: `general-purpose`

Use for all standard workloads (data exploration, SQL, non-GPU notebooks).

| Item | Value |
|:---|:---|
| Cluster ID | *(look up via `databricks clusters list --profile <PROFILE>`)* |
| Runtime | 17.3 LTS (Spark 4.0.0, Scala 2.13) |
| Worker type | Standard_D8ads_v5 (32 GB, 8 cores) |
| Autoscaling | 1–12 workers |
| Idle termination | 60 min |
| Access mode | Standard |
| Unity Catalog | ✓ |

### GPU/ML: `machine-learning (gpu)`

Use for GPU-accelerated training, inference, and embedding workloads.

| Item | Value |
|:---|:---|
| Cluster ID | `0303-075313-aono4t6a` |
| Runtime | 17.3 LTS (Spark 4.0.0, Scala 2.13) |
| Node type | Standard_NV36ads_A10_v5 (440 GB, 1× A10 GPU, 36 cores) |
| Mode | Single node |
| Idle termination | 60 min |
| Access mode | Dedicated — `bms_dev` |
| Unity Catalog | ✓ |

## Running Notebooks on the Cluster

Upload a local `.py` notebook to the Databricks workspace and execute it on
the cluster via the generic runner job, with automatic error fixing and retry.

**Default cluster:** `general-purpose` — use `machine-learning (gpu)` only when GPU acceleration is needed.

### Config

| Item | Value |
|:---|:---|
| Profile | `premium` |
| Runner job ID | `194658749253431` |
| Workspace base | `/Users/dominik.peter@bmsuisse.ch/AIActionPlan/notebooks/` |
| Cluster ID (default) | *(general-purpose — see Clusters section above)* |
| Cluster ID (GPU) | `0303-075313-aono4t6a` |
| Max retries | 3 |

### Steps

**1. Derive workspace path** — strip `.py`, keep filename:
```
local:     notebooks/3.1-sales-visit-scoring.py
workspace: /Users/dominik.peter@bmsuisse.ch/AIActionPlan/notebooks/3.1-sales-visit-scoring
```

**2. Upload:**
```bash
databricks workspace import "<WORKSPACE_PATH>" \
  --file "<LOCAL_PATH>" --format SOURCE --language PYTHON \
  --overwrite --profile premium
```

**3. Trigger:**
```bash
databricks jobs run-now --profile premium --json '{
  "job_id": 194658749253431,
  "notebook_params": {"notebook_path": "<WORKSPACE_PATH>"}
}'
```

Capture both the top-level `run_id` and `tasks[0].run_id` (task run ID) from the response.

**4. Check result** — look at `state.result_state`: `SUCCESS` → done, `FAILED` → fix and retry.

**5. Fetch error** using the **task** run_id:
```bash
databricks api get "/api/2.1/jobs/runs/get-output" \
  --profile premium --json '{"run_id": <TASK_RUN_ID>}'
```
Read `error` (short) and `error_trace` (full traceback).

**6. Fix and retry** — read the local notebook, fix the root cause, re-upload, rerun. After 3 failed attempts stop and explain what was tried.

### Common error fixes

| Error | Fix |
|:---|:---|
| `ModuleNotFoundError` | Add `%pip install <pkg>` at top of notebook |
| `Table not found` | Verify with SQL query below |
| `KeyError` / `ColumnNotFound` | Inspect schema with SQL |
| `FileNotFoundError` (DBFS) | Verify path on DBFS |
| Syntax error | Fix the offending line |

## Ad-hoc Job Submit

Run a notebook (or Python script already uploaded to the workspace) directly as a one-time job — no runner job wrapper needed.

⚠️ The CLI uses a **tasks array**, not top-level `existing_cluster_id` / `notebook_task`.

```bash
databricks jobs submit --profile premium --json '{
  "run_name": "my_ad_hoc_run",
  "tasks": [{
    "task_key": "main",
    "existing_cluster_id": "<CLUSTER_ID>",
    "notebook_task": {
      "notebook_path": "<WORKSPACE_PATH>",
      "base_parameters": {"sample": "500", "epochs": "1"}
    }
  }]
}'
```

Capture the `run_id` from the response, then poll and fetch output the same way as the runner job (steps 4–6 above).

**For Python scripts** (not notebooks), use `spark_python_task` instead:

```bash
databricks jobs submit --profile premium --json '{
  "run_name": "my_script_run",
  "tasks": [{
    "task_key": "main",
    "existing_cluster_id": "<CLUSTER_ID>",
    "spark_python_task": {
      "python_file": "<WORKSPACE_PATH>.py",
      "parameters": ["--sample", "500"]
    }
  }]
}'
```

## Running Code on the Cluster

**Use `scripts/run.py`** — a single command that opens a context, executes
Python or SQL, polls for the result, prints output, and cleans up.

```bash
# Python — inline
uv run scripts/run.py \
  --profile premium \
  --cluster-id <CLUSTER_ID> \
  --lang python \
  --code "print(spark.version)"

# Python — from a local file (language inferred from .py extension)
uv run scripts/run.py \
  --profile premium \
  --cluster-id <CLUSTER_ID> \
  --file path/to/script.py

# SQL
uv run scripts/run.py \
  --profile premium \
  --cluster-id <CLUSTER_ID> \
  --lang sql \
  --code "SELECT * FROM catalog.schema.table LIMIT 10"

# Pass arguments to a Python script (injected as ARGS dict)
uv run scripts/run.py \
  --profile premium \
  --cluster-id <CLUSTER_ID> \
  --file migrate.py \
  --args '{"catalog": "prod", "dry_run": true}'
```

Inside the script, read from `ARGS` instead of `sys.argv`:
```python
catalog = ARGS["catalog"]
dry_run = ARGS.get("dry_run", False)
```

**Flags**

| Flag | Default | Description |
|:---|:---|:---|
| `--profile` | *(required)* | Databricks CLI profile |
| `--cluster-id` | *(required)* | Cluster to run on |
| `--lang` | inferred from file ext | `python` \| `sql` \| `r` \| `scala` |
| `--code` | — | Inline code string (mutually exclusive with `--file`) |
| `--file` | — | Local script file |
| `--args` | — | JSON dict injected as `ARGS` variable (Python only) |
| `--poll-interval` | `2.0` | Seconds between status polls |
| `--no-destroy` | off | Keep context open after run |

Stdout goes to stdout; errors and tracebacks go to stderr with a non-zero exit code.

## Running SQL on the Cluster

Use the execution context API to run SQL directly on the cluster — full Spark +
Unity Catalog access, no separate warehouse needed. Prefer this over the SQL
warehouse when debugging notebook errors (same Spark session, sees temp views
and uncommitted Delta writes).

Use `general-purpose` for standard SQL; use `machine-learning (gpu)` (`0303-075313-aono4t6a`) for GPU workloads.

```bash
# 1. Create context (use general-purpose cluster ID; swap for GPU cluster if needed)
databricks api post /api/1.2/contexts/create --profile premium \
  --json '{"clusterId": "<CLUSTER_ID>", "language": "python"}'

# 2. Execute (use spark.sql() for SQL, or any Python)
databricks api post /api/1.2/commands/execute --profile premium --json '{
  "clusterId": "<CLUSTER_ID>",
  "contextId": "<CONTEXT_ID>",
  "language": "python",
  "command": "spark.sql(\"SELECT * FROM transf.sales LIMIT 5\").show(truncate=False)"
}'

# 3. Poll until status = Finished
databricks api get /api/1.2/commands/status --profile premium --json '{
  "clusterId": "0303-075313-aono4t6a",
  "contextId": "<CONTEXT_ID>",
  "commandId": "<COMMAND_ID>"
}'
```

Useful diagnostic queries:
```python
spark.sql("DESCRIBE EXTENDED <catalog>.<schema>.<table>").show(truncate=False)
spark.sql("SELECT * FROM <table> LIMIT 10").show(truncate=False)
spark.sql("SHOW TABLES IN <schema>").show()
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| `cannot configure default credentials` | Use `--profile` flag or authenticate first |
| `PERMISSION_DENIED` | Check workspace/UC permissions |
| `RESOURCE_DOES_NOT_EXIST` | Verify resource name/id and profile |

## Required Reading by Task

| Task | READ BEFORE proceeding |
|------|------------------------|
| First time setup | [CLI Installation](databricks-cli-install.md) |
| Auth issues / new workspace | [CLI Authentication](databricks-cli-auth.md) |
| Exploring tables/schemas | [Data Exploration](data-exploration.md) |
| Deploying jobs/pipelines | [Asset Bundles](asset-bundles.md) |

## Reference Guides

- [Databricks CLI docs](https://docs.databricks.com/aws/en/dev-tools/cli) — official CLI reference (commands, flags, auth, bundles)
- [Databricks llms.txt](https://docs.databricks.com/llms.txt) — machine-readable index of all Databricks docs
- [CLI Installation](databricks-cli-install.md)
- [CLI Authentication](databricks-cli-auth.md)
- [Data Exploration](data-exploration.md)
- [Asset Bundles](asset-bundles.md)
- [Databricks SQL CLI (Azure docs)](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-sql-cli) — SQL CLI options, authentication methods, and output formats
