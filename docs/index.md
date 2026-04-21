---
title: BMS Skills
description: Reusable AI agent skills for the BMSuisse engineering team.
---

# BMS Skills

Reusable AI agent skills for the BMSuisse engineering team — composable instructions that extend coding agents (Claude Code, Cursor, Codex CLI) with company-specific workflows and best practices.

## What are skills?

A **skill** is a `SKILL.md` file containing instructions, examples, and conventions scoped to a specific domain. When active, a skill gives your agent:

- Deep knowledge of the stack (e.g. TanStack Router patterns, FastAPI conventions)
- Team conventions (e.g. use `uv` not `pip`, use `ty` not `pyright`)
- Automated tool remapping via PreToolUse hooks

Skills activate in two ways:

1. **Slash command** — `/coding-guidelines-python` explicitly loads the skill
2. **Auto-trigger** — Claude Code detects from context that a skill is relevant and loads it automatically

## Quick install

Add to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "bmsuisse-skills": {
      "source": {
        "source": "github",
        "repo": "bmsuisse/skills"
      }
    }
  },
  "enabledPlugins": {
    "coding@bmsuisse-skills": true
  }
}
```

See [Installation](installation.md) for all plugins and project-scoped setup.

## Available plugins

| Plugin | What's inside |
|---|---|
| `coding` | Python, TypeScript, TanStack, FastAPI, Postgres, autoresearch, init-app-stack |
| `databricks` | Databricks CLI, Spark Connect |
| `ui` | KendoReact |
| `writing` | Remove AI slop, scientific revision |
| `bms` | Master skill — all core standards via `/bms` |
| `caveman` | Ultra-compressed communication (~75% token reduction) |
| `azure-deploy` | Azure deployments via azd/terraform/az |
| `azure-diagnostics` | Azure production diagnostics |

## Automatic tool remapping

The `coding` and `bms` plugins ship with **PreToolUse hooks** that silently rewrite shell commands:

| You type | Agent runs |
|---|---|
| `python script.py` | `uv run python script.py` |
| `pip install foo` | `uv add foo` |
| `pytest` | `uv run pytest` |
| `ty` | `uv run ty` |
| `npm install foo` | `bun add foo` |
| `npx foo` | `bunx foo` |
