---
title: Installation
description: How to install BMS Skills in Claude Code and other agents.
---

# Installation

## Claude Code — Plugin (recommended)

### 1. Register the marketplace

Add to `~/.claude/settings.json` (global, applies to all projects):

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

### 2. Enable plugins

Add the plugins you want to `enabledPlugins`:

```json
{
  "enabledPlugins": {
    "coding@bmsuisse-skills": true,
    "databricks@bmsuisse-skills": true,
    "ui@bmsuisse-skills": true,
    "writing@bmsuisse-skills": true,
    "bms@bmsuisse-skills": true,
    "caveman@bmsuisse-skills": true,
    "azure-deploy@bmsuisse-skills": true,
    "azure-diagnostics@bmsuisse-skills": true
  }
}
```

Or use the Claude Code command palette:

```
/plugin marketplace add bmsuisse/skills
/plugin install coding@bmsuisse-skills
```

### Plugin reference

| Plugin | Skills included | Install command |
|---|---|---|
| `coding` | autoresearch, coding-guidelines-python, coding-guidelines-typescript, deslop, fastapi-guideline, init-app-stack, postgres-best-practices, postgres-test-setup, sql-optimization, tanstack-best-practices | `coding@bmsuisse-skills` |
| `databricks` | databricks-cli, spark-connect | `databricks@bmsuisse-skills` |
| `ui` | kendo-ui-react | `ui@bmsuisse-skills` |
| `writing` | remove-ai-writing, scientific-revision | `writing@bmsuisse-skills` |
| `bms` | bms master + all core standards | `bms@bmsuisse-skills` |
| `caveman` | caveman, caveman-review, caveman-commit | `caveman@bmsuisse-skills` |
| `azure-deploy` | azure-deploy | `azure-deploy@bmsuisse-skills` |
| `azure-diagnostics` | azure-diagnostics | `azure-diagnostics@bmsuisse-skills` |

## Per-project setup

To enable skills only for a specific project, add to `.claude/settings.json` in your project root (commit this file):

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

This is the recommended setup when scaffolding a new app with `init-app-stack` — the companion skills install alongside the project.

## skills CLI (other agents)

Install a specific skill into any agent platform:

```bash
npx skills add https://github.com/bmsuisse/skills --skill <skill-name>
```

Install all skills:

```bash
npx skills add https://github.com/bmsuisse/skills
```

The CLI auto-detects your platform:

| Platform | Directory |
|---|---|
| Claude Code | `.claude/skills/` |
| Cursor | `.cursor/rules/` |
| Codex CLI | `~/.codex/skills/` |
| Gemini CLI | auto-detected |

## Verify

Start a new Claude Code session and type `/` — you should see the installed skills in the command list. Or ask Claude to check:

```
What skills do you have active?
```
