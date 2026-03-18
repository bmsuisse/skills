# Company Skills

A collection of reusable AI agent skills for our engineering team. Skills are composable instructions that extend coding agents (Antigravity, Claude Code, Cursor, etc.) with company-specific workflows and best practices.

## Available Skills

| Skill | Description |
|---|---|
| [init-app-stack](./skills/init-app-stack/) | Bootstrap a Nuxt + Nuxt UI (bun) frontend with a FastAPI (uv) backend |

## Installation

### Antigravity / Claude Code

Install a specific skill:

```bash
npx skills add https://github.com/<your-org>/<this-repo> --skill <skill-name>
```

Install all skills:

```bash
npx skills add https://github.com/<your-org>/<this-repo>
```

Browse skills online at: `https://skills.sh/<your-org>/<this-repo>/<skill-name>`

### Verify Installation

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
3. Use the `skill-creator` skill to iterate and test
4. Open a PR

## Repo Structure

```
.
├── skills/                   ← canonical skill sources (installed via npx skills add)
│   └── <skill-name>/
│       └── SKILL.md
├── .agents/skills/           ← runtime: Antigravity picks up skills from here
│   └── <skill-name>/
├── .claude/skills/           ← runtime: Claude Code picks up skills from here (symlink)
│   └── <skill-name>/
└── skills-lock.json          ← tracks installed third-party skills
```

> **Note:** When adding a new skill, add it to `skills/` (canonical), `.agents/skills/` (Antigravity runtime), and `.claude/skills/` (Claude Code runtime). The `add-skill` workflow script handles this automatically.

## Updating Third-Party Skills

```bash
npx skills update
```
