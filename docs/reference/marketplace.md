---
title: Marketplace & Plugins
description: Full reference for the bmsuisse-skills marketplace — all plugins, skills, and third-party references.
---

# Marketplace & Plugins

## Register the marketplace

```json
{
  "extraKnownMarketplaces": {
    "bmsuisse-skills": {
      "source": {
        "source": "github",
        "repo": "bmsuisse/skills"
      }
    }
  }
}
```

## All plugins

### `coding`

General development skills.

| Skill | Description |
|---|---|
| `autoresearch` | Autonomous iterative experiment loop |
| `coding-guidelines-python` | Python typing, ty, dataclasses, enums |
| `coding-guidelines-typescript` | TS strictness, discriminated unions, async |
| `deslop` | Remove AI slop from code and PRs |
| `fastapi-guideline` | FastAPI + Granian + asyncpg patterns |
| `init-app-stack` | Scaffold Vite + React + TanStack + FastAPI |
| `postgres-best-practices` | Raw asyncpg, t-string SQL, transactions |
| `postgres-test-setup` | Docker Postgres for integration tests |
| `sql-optimization` | Query tuning, indexes, explain plans |
| `tanstack-best-practices` | TanStack Router + Query patterns |

```json
"coding@bmsuisse-skills": true
```

### `databricks`

Databricks and Spark skills.

| Skill | Description |
|---|---|
| `databricks-cli` | Auth, clusters, jobs, bundles |
| `spark-connect` | Local PySpark against remote cluster |

```json
"databricks@bmsuisse-skills": true
```

### `ui`

UI framework skills.

| Skill | Description |
|---|---|
| `kendo-ui-react` | KendoReact Grid, Form, theming, pitfalls |

```json
"ui@bmsuisse-skills": true
```

### `fabricks-data`

Fabricks / data platform skills.

| Skill | Description |
|---|---|
| `fabricks-glossary` | Company-specific jargon and domain terms |
| `fabricks-sql-analyzer` | SQL dependency DAG and performance analysis |

```json
"fabricks-data@bmsuisse-skills": true
```

### `writing`

Writing and documentation skills.

| Skill | Description |
|---|---|
| `remove-ai-writing` | Fix AI writing patterns in EN/DE/FR/IT |
| `scientific-revision` | Revise academic papers for clarity and precision |

```json
"writing@bmsuisse-skills": true
```

### `bms`

Master skill — activates all core BMSuisse standards.

```json
"bms@bmsuisse-skills": true
```

Use `/bms`, `/bms sql`, `/bms python`, `/bms data`.

### `caveman` *(JuliusBrussee/caveman)*

Ultra-compressed communication mode. Cuts token usage ~75%.

```json
"caveman@bmsuisse-skills": true
```

### `azure-deploy` *(microsoft/azure-skills)*

Azure deployments via azd/terraform/az with pre-deploy validation and RBAC checks.

```json
"azure-deploy@bmsuisse-skills": true
```

### `azure-diagnostics` *(microsoft/azure-skills)*

Azure production diagnostics via AppLens, Monitor, and resource health.

```json
"azure-diagnostics@bmsuisse-skills": true
```

## Plugin management commands

```bash
/plugin marketplace add bmsuisse/skills
/plugin install coding@bmsuisse-skills
/plugin disable coding@bmsuisse-skills
/plugin uninstall coding@bmsuisse-skills
/reload-plugins
```
