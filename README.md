# Company Skills

A collection of reusable AI agent skills for our engineering team. Skills are composable instructions that extend coding agents (Antigravity, Claude Code, Cursor, etc.) with company-specific workflows and best practices.

## Available Skills

| Skill | Description |
|---|---|
| [init-app-stack](./skills/init-app-stack/) | Bootstrap a Nuxt + Nuxt UI (bun) frontend with a FastAPI (uv) backend |

## Installation

The `skills` CLI ([github.com/vercel-labs/skills](https://github.com/vercel-labs/skills)) reads directly from GitHub — no registration needed.

### Install a specific skill

```bash
npx skills add https://github.com/bmsuisse/skills --skill <skill-name>
```

### Install all skills

```bash
npx skills add https://github.com/bmsuisse/skills
```

The CLI auto-detects your agent platform and installs into the right directory:

| Platform | Directory |
|---|---|
| Antigravity | `.agents/skills/` or `.agent/skills/` |
| Claude Code | `.claude/skills/` |
| Cursor | `.cursor/rules/` |
| Codex CLI | `~/.codex/skills/` |
| Gemini CLI | auto-detected |

### Browse on skills.sh

```
https://skills.sh/bmsuisse/skills/<skill-name>
```

> **Note:** The URL works immediately after the first `npx skills add` is run. The skill appears on the [skills.sh leaderboard](https://skills.sh) automatically based on install telemetry — no manual registration required.

### Verify installation

Start a new session and ask your agent something that should trigger the skill. It should automatically invoke the relevant skill.

## Adding a New Skill

Each skill lives in its own directory under `skills/`:

```
skills/
└── your-skill-name/
    ├── SKILL.md          ← required: instructions + YAML frontmatter
    ├── scripts/          ← optional: helper scripts
    ├── references/       ← optional: reference documentation
    └── assets/           ← optional: templates, icons, etc.
```

### SKILL.md format

```markdown
---
name: your-skill-name
description: What the skill does and when to trigger it. Be specific — this is how the agent decides whether to use it.
---

# Your Skill

Instructions for the agent to follow...
```

### Workflow

1. Create a branch: `git checkout -b skill/<skill-name>`
2. Create `skills/<skill-name>/SKILL.md`
3. Open a PR — merging syncs to all runtime directories

## Repo Structure

```
.
├── skills/                   ← canonical skill sources (what npx skills add reads)
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── scripts/
│       └── references/
├── .agents/skills/           ← runtime: Antigravity
├── .agent/skills/            ← runtime: Antigravity (alternate)
├── .claude/skills/           ← runtime: Claude Code
└── skills-lock.json          ← tracks installed third-party skills
```

> **Note:** When adding a skill, run `/add-skill` — it adds to `skills/` (canonical) and syncs to all runtime directories automatically.

## Updating Third-Party Skills

```bash
npx skills update
```
