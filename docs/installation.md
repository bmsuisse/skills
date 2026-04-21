---
title: Installation
description: Install BMS Skills in Claude Code or any other AI agent.
---

# Installation

## Claude Code — Plugin (recommended)

The plugin approach installs skills directly into Claude Code and keeps them up to date automatically.

### 1. Add to `~/.claude/settings.json`

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
    "coding@bmsuisse-skills": true,
    "databricks@bmsuisse-skills": true,
    "ui@bmsuisse-skills": true,
    "writing@bmsuisse-skills": true,
    "bms@bmsuisse-skills": true,
    "caveman@bmsuisse-skills": true
  }
}
```

Or via the Claude Code command palette:

```
/plugin marketplace add bmsuisse/skills
/plugin install coding@bmsuisse-skills
```

### 2. Reload

```
/reload-plugins
```

Skills are now active. Type `/` to see available slash commands.

### Plugin reference

| Plugin | Skills | Use for |
|---|---|---|
| `coding` | Python, TypeScript, TanStack, FastAPI, Azure auth, Postgres, autoresearch, init-app-stack | General dev work |
| `databricks` | databricks-cli, spark-connect | Databricks & Spark |
| `ui` | kendo-ui-react | KendoReact components |
| `writing` | remove-ai-writing, scientific-revision | Writing & docs |
| `bms` | Master skill + all core standards | All standards via `/bms` |
| `caveman` | caveman, caveman-review, caveman-commit | Token-efficient comms |
| `azure-deploy` | azure-deploy | Azure deployments |
| `azure-diagnostics` | azure-diagnostics | Azure diagnostics |

## Per-project setup

To scope skills to one project, add `.claude/settings.json` to the project root and commit it:

```json
{
  "extraKnownMarketplaces": {
    "bmsuisse-skills": {
      "source": { "source": "github", "repo": "bmsuisse/skills" }
    }
  },
  "enabledPlugins": {
    "coding@bmsuisse-skills": true
  }
}
```

The `init-app-stack` scaffold generates this file automatically with the right plugins for the stack.

## skills CLI — Cursor, Copilot, Codex, others

### Prerequisites

**Node.js 18+** and **npm** are required. Check:

```bash
node --version   # needs 18+
npm --version
```

Download Node.js (LTS) from [nodejs.org](https://nodejs.org) if needed — npm is bundled.

### Install

No global install required — `npx` fetches the CLI on demand:

```bash
# All skills
npx skills add bmsuisse/skills

# One specific skill
npx skills add bmsuisse/skills --skill coding-guidelines-python

# Update previously installed skills
npx skills update
```

### Platform detection

The CLI detects your agent from config files in the current directory:

| Detected | Platform | Writes to |
|---|---|---|
| `.claude/` | Claude Code | `.claude/skills/` |
| `.cursor/` or `.cursorrules` | Cursor | `.cursor/rules/` |
| `.github/copilot-instructions.md` | GitHub Copilot | `.github/instructions/` |
| `AGENTS.md` or `.codex/` | Codex CLI | `.codex/skills/` |
| `.gemini/` | Gemini CLI | `.gemini/skills/` |

### Telemetry opt-out

```bash
DISABLE_TELEMETRY=1 npx skills add bmsuisse/skills
```

## Verify

Start a new Claude Code session and type `/` — installed skills appear in the list. Or ask:

```
What skills do you have active?
```
