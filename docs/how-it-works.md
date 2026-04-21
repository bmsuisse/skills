---
title: How It Works
description: How skills activate, how hooks work, and how the plugin system fits together.
---

# How It Works

## Skills

A skill is a Markdown file (`SKILL.md`) with YAML frontmatter:

```markdown
---
name: fastapi-guideline
description: Use this skill whenever working with FastAPI...
---

# FastAPI
Instructions for the agent...
```

The `description` field is what the agent reads to decide whether to load the skill. Keep it specific — the more clearly it describes *when* to trigger, the more reliably it auto-activates.

## Loading system

Skills use three-level progressive loading:

```
1. description (~100 words)   → always in context
2. SKILL.md body              → loaded when skill triggers
3. references/ files          → loaded on demand
```

This keeps the agent's context lean. Heavy reference material stays on disk until it's actually needed.

## Auto-triggering

When you send a message, Claude reads all installed skill descriptions and decides which ones are relevant. If a skill's description matches what you're doing — even without a slash command — it loads the full `SKILL.md` automatically.

Example: you write `"add asyncpg connection pooling to my FastAPI app"` — the `fastapi-guideline` and `postgres-best-practices` skills activate without you typing anything.

## Slash commands

Every skill is also available as a slash command. Type `/` in Claude Code to see all installed skills:

```
/coding-guidelines-python
/init-app-stack
/spark-connect
/autoresearch
/bms
```

## Hooks

The `coding` and `bms` plugins ship **PreToolUse hooks** — shell scripts that run before Claude executes a Bash command. They intercept common tool invocations and rewrite them to preferred tools:

- `pip install` → `uv add`
- `npm run dev` → `bun run dev`
- `pytest` → `uv run pytest`

The rewrite is silent. The agent sees the corrected command as if it typed it.

A separate global hook rewrites `pyright` → `uv run ty check`, since `ty` is the team's standard type checker.

## Plugins

Skills are bundled into **plugins** for easier distribution. A plugin is a named group of skills that install together.

The `bmsuisse-skills` marketplace (this repo) defines all available plugins. When you enable `coding@bmsuisse-skills`, all skills in that plugin become available in your Claude Code session.

Plugin definitions live in `.claude-plugin/marketplace.json`.

## File locations

After installation, skills land here:

| Platform | Path |
|---|---|
| Claude Code | `.claude/skills/` (project) or `~/.claude/skills/` (global) |
| Cursor | `.cursor/rules/` |
| Codex CLI | `~/.codex/skills/` |

## Contributing a skill

1. Create `skills/<skill-name>/SKILL.md`
2. Add it to the relevant plugin in `.claude-plugin/marketplace.json`
3. Open a PR — CI auto-updates the skills table in README
