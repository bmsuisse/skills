---
title: BMS Skills
description: Reusable AI agent skills for the BMSuisse engineering team.
---

# BMS Skills

**Skills** are reusable instruction sets that extend AI coding agents with team-specific workflows, conventions, and domain knowledge.

Instead of explaining your stack to the agent every session, you install a skill once — and it activates automatically whenever it's relevant.

## What a skill does

A skill is a `SKILL.md` file that tells the agent:

- **What conventions to follow** — e.g. use `uv` not `pip`, use `ty check` not `pyright`, no ORM
- **What patterns to apply** — e.g. asyncpg t-string SQL, TanStack query key factories, FastAPI lifespan pools
- **What to watch out for** — common pitfalls, anti-patterns, project-specific constraints

Skills activate in two ways:

**1. Slash command** — explicitly invoke any skill:
```
/coding-guidelines-python
/spark-connect
/init-app-stack
```

**2. Auto-trigger** — the agent reads the skill description and loads it automatically when the context matches. You don't have to do anything — if you're writing FastAPI code and the `fastapi-guideline` skill is installed, the agent picks it up.

## What's included

Skills are grouped into **plugins** by domain:

| Plugin | What's inside |
|---|---|
| `coding` | Python guidelines, TypeScript guidelines, TanStack, FastAPI, Azure auth, Postgres, autoresearch, init-app-stack scaffold |
| `databricks` | Databricks CLI, Spark Connect version alignment |
| `ui` | KendoReact components |
| `writing` | Remove AI slop, scientific revision |
| `bms` | Master skill — all core standards via `/bms` |
| `caveman` | Ultra-compressed communication (~75% fewer tokens) |
| `azure-deploy` | Azure deployments via azd / terraform |
| `azure-diagnostics` | Azure production diagnostics |

→ [Install now](installation.md)

## Automatic tool remapping

The `coding` and `bms` plugins ship with **PreToolUse hooks** that silently rewrite shell commands before the agent runs them:

| You type | Agent runs |
|---|---|
| `python script.py` | `uv run python script.py` |
| `pip install foo` | `uv add foo` |
| `pytest` | `uv run pytest` |
| `npm install foo` | `bun add foo` |
| `npx foo` | `bun x foo` |

No config needed — hooks activate automatically when a plugin is installed.
