---
title: PreToolUse Hooks
description: Automatic tool remapping — how the hooks work and what they rewrite.
---

# PreToolUse Hooks

The `coding` and `bms` plugins ship with **PreToolUse hooks** that silently rewrite shell commands before Claude executes them. No config needed — hooks activate the moment a plugin is installed.

## Tool remapping

### Python / uv

| You type | Agent runs |
|---|---|
| `python script.py` | `uv run python script.py` |
| `python -m pytest` | `uv run -m pytest` |
| `python3 -m module` | `uv run -m module` |
| `pip install foo` | `uv add foo` |
| `pip uninstall foo` | `uv remove foo` |
| `pytest` | `uv run pytest` |
| `ruff check .` | `uv run ruff check .` |
| `ty check` | `uv run ty check` |

### Node / bun

| You type | Agent runs |
|---|---|
| `npm install` | `bun install` |
| `npm install foo` | `bun add foo` |
| `npm install -D foo` | `bun add -d foo` |
| `npm run dev` | `bun run dev` |
| `npm uninstall foo` | `bun remove foo` |
| `npx foo` | `bunx foo` |
| `pnpm add foo` | `bun add foo` |
| `yarn add foo` | `bun add foo` |

### pyright → ty

A separate global hook (in `~/.claude/settings.json`) rewrites `pyright` to `ty check`:

| You type | Agent runs |
|---|---|
| `pyright` | `ty check` |
| `uv run pyright` | `uv run ty check` |

## How it works

Hooks receive tool input as JSON on stdin and can return `hookSpecificOutput.updatedInput` to rewrite the command before it executes. The agent sees only the rewritten command — the rewrite is transparent.

```json
// Input to hook
{ "tool_input": { "command": "npm install react" } }

// Hook output
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "updatedInput": { "command": "bun add react" }
  }
}
```

## Adding your own hooks

Add to `.claude/settings.json` in your project:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "your-rewrite-script-here"
      }]
    }]
  }
}
```
