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

## skills CLI (Cursor, Copilot, Codex, and other agents)

The `skills` CLI installs skills from any GitHub repo into any AI agent platform — no account needed, no global install required.

### Prerequisites

You need **Node.js 18+** and **npm** (or any compatible package manager). Check:

```bash
node --version   # needs 18+
npm --version
```

If you don't have Node.js, download it from [nodejs.org](https://nodejs.org) (LTS version). npm is bundled with Node.js — no separate install needed.

You do **not** need to install the `skills` package globally. `npx` downloads and runs it on demand:

```bash
# npx downloads skills automatically on first run
npx skills add bmsuisse/skills
```

### Install all skills

```bash
npx skills add bmsuisse/skills
```

This downloads every skill from this repo and writes it into the correct directory for your agent platform (auto-detected — see below).

### Install a specific skill

```bash
npx skills add bmsuisse/skills --skill coding-guidelines-python
npx skills add bmsuisse/skills --skill spark-connect
npx skills add bmsuisse/skills --skill tanstack-best-practices
```

### How platform detection works

The CLI looks for config files and directories in the current working directory to identify which agent is in use:

| Detected file / folder | Platform | Skills written to |
|---|---|---|
| `.claude/` or `.claude/settings.json` | Claude Code | `.claude/skills/` |
| `.cursor/` or `.cursorrules` | Cursor | `.cursor/rules/` |
| `.github/copilot-instructions.md` | GitHub Copilot | `.github/instructions/` |
| `AGENTS.md` or `.codex/` | Codex CLI | `.codex/skills/` |
| `.gemini/` | Gemini CLI | `.gemini/skills/` |
| `CLAUDE.md` (root) | Claude Code (root) | `.claude/skills/` |

If multiple platforms are detected, the CLI asks which one to install into. If none is detected, it falls back to creating `.claude/skills/` (the most common case).

### What gets written

For each skill, the CLI writes a `SKILL.md` file into the target directory:

```
.claude/skills/
├── coding-guidelines-python.md
├── coding-guidelines-typescript.md
├── tanstack-best-practices.md
└── spark-connect.md
```

The agent platform reads these files at startup and makes the skills available as slash commands and auto-triggers.

### Update installed skills

```bash
npx skills update
```

Re-downloads all previously installed skills from their source repos and overwrites the local copies with the latest version.

### Disable telemetry

The CLI collects anonymous install telemetry (skill name + timestamp) by default. Opt out:

```bash
DISABLE_TELEMETRY=1 npx skills add bmsuisse/skills
```

Or set permanently in your shell profile:

```bash
export DISABLE_TELEMETRY=1
```

### Browse on skills.sh

Every skill in this repo is listed at:

```
https://skills.sh/bmsuisse/skills
https://skills.sh/bmsuisse/skills/<skill-name>
```

The leaderboard updates automatically based on install telemetry.

## Verify

Start a new Claude Code session and type `/` — you should see the installed skills in the command list. Or ask Claude to check:

```
What skills do you have active?
```
