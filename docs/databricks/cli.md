---
title: Databricks CLI
description: Databricks CLI operations — auth, profiles, clusters, bundles, and notebook execution.
---

# Databricks CLI

**Skill:** `databricks-cli` · **Plugin:** `databricks@bmsuisse-skills`

## Auth

```bash
databricks auth login --profile <profile-name>
databricks auth profiles          # list configured profiles
```

## Clusters

```bash
databricks clusters list --profile <profile>
databricks clusters get --cluster-id <id> --profile <profile>
databricks clusters start --cluster-id <id> --profile <profile>

# Get DBR version
databricks clusters get --cluster-id <id> --profile <profile> \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d['spark_version'])"
```

## Jobs

```bash
databricks jobs list --profile <profile>
databricks jobs run-now --job-id <id> --profile <profile>
databricks runs get --run-id <id> --profile <profile>
```

## Notebooks

```bash
databricks workspace list /path --profile <profile>
databricks workspace export /path/notebook --profile <profile> --format SOURCE
```

## Bundles (DAB)

```bash
databricks bundle validate
databricks bundle deploy --target dev
databricks bundle run <job-name> --target dev
```

## `.env` pattern

```bash
DATABRICKS_PROFILE=my-profile
DATABRICKS_CLUSTER_ID=1234-567890-abc123
```

Load before using Databricks Connect:

```python
from dotenv import load_dotenv
load_dotenv()
```
