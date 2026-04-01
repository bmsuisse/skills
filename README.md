```ansi
 ██████╗ ███╗   ███╗███████╗    ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
 ██╔══██╗████╗ ████║██╔════╝    ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
 ██████╔╝██╔████╔██║███████╗    ███████╗█████╔╝ ██║██║     ██║     ███████╗
 ██╔══██╗██║╚██╔╝██║╚════██║    ╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
 ██████╔╝██║ ╚═╝ ██║███████║    ███████║██║  ██╗██║███████╗███████╗███████║
 ╚═════╝ ╚═╝     ╚═╝╚══════╝    ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝
 ```

> Reusable AI agent skills for our engineering team — composable instructions that extend coding agents (Claude Code, Cursor, Codex CLI, etc.) with company-specific workflows and best practices.

---

## 📦 Available Skills

<!-- SKILLS_TABLE_START -->
| Skill | Description |
|---|---|
| [databricks-cli](./skills/fabricks_data/databricks-cli/) | Databricks CLI operations: auth, profiles, data exploration, bundles, and notebook execution. Use this skill for ANY… |
| [fabricks-glossary](./skills/fabricks_data/fabricks-glossary/) | Use this skill whenever company-specific jargon, acronyms, or domain terminology is needed to answer correctly. |
| [fabricks-sql-analyzer](./skills/fabricks_data/fabricks-sql-analyzer/) | Analyzes all SQL files in the Fabricks.Runtime repository, builds a dependency DAG, runs performance heuristics, and… |
| [codeunit-analyzer](./skills/programming/codeunit-analyzer/) | Comprehensive C-AL performance analyzer for Classic Microsoft Dynamics NAV (Navision). Targets Classic NAV anti-patte… |
| [coding-guidelines](./skills/programming/coding-guidelines/) | Apply and enforce project coding standards during any code generation, review, or refactoring session. Use this skill… |
| [coding-guidelines-python](./skills/programming/coding-guidelines-python/) | Apply and enforce Python-specific coding standards. Use alongside coding-guidelines for any Python file — covers typi… |
| [coding-guidelines-typescript](./skills/programming/coding-guidelines-typescript/) | Apply and enforce TypeScript-specific coding standards. Use alongside coding-guidelines for any TypeScript file — cov… |
| [deslop](./skills/programming/deslop/) | Remove AI slop from code and pull requests. Use this skill whenever the user wants to clean up AI-generated code, rev… |
| [fastapi-guideline](./skills/programming/fastapi-guideline/) | Use this skill whenever working with FastAPI — building APIs, adding routes, structuring projects, streaming response… |
| [init-app-stack](./skills/programming/init-app-stack/) | Use this skill whenever the user wants to bootstrap, scaffold, or initialize a new full-stack app with a Nuxt + Nuxt… |
| [postgres-best-practices](./skills/programming/postgres-best-practices/) | PostgreSQL coding standards for Python projects using psycopg (no ORM). Use this skill whenever the user is writing o… |
| [postgres-test-setup](./skills/programming/postgres-test-setup/) | Set up and work with a local PostgreSQL test database in Docker for integration/e2e tests. Use this skill whenever th… |
| [sql-optimization](./skills/programming/sql-optimization/) | "Universal SQL performance optimization assistant for comprehensive query tuning, indexing strategies, and database p… |
| [scientific-revision](./skills/scientific-revision/) | Use this skill whenever the user wants to verify, revise, or improve a scientific essay, academic paper, or any writt… |
<!-- SKILLS_TABLE_END -->

---

## 🚀 Installation

### Claude Code Plugin

Add to `~/.claude/settings.json` to install all plugins:

```json
{
  "extraKnownMarketplaces": {
    "bmsuisse-skills": {
      "source": {
        "source": "github",
        "repo": "bmsuisse/skills",
        "ref": "main",
        "sparsePaths": [".claude-plugin"]
      }
    }
  },
  "enabledPlugins": {
    "skills@bmsuisse-skills": true,
    "fabricks-data@bmsuisse-skills": true
  }
}
```

| Plugin | Contents |
|---|---|
| `skills@bmsuisse-skills` | Programming skills + uv command hook |
| `fabricks-data@bmsuisse-skills` | Fabricks / Databricks skills + uv command hook |

Restart Claude Code after editing the file — it will fetch the plugins automatically.

---

### skills CLI

The `skills` CLI reads directly from GitHub — no registration needed.

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
| Claude Code | `.claude/skills/` |
| Cursor | `.cursor/rules/` |
| Codex CLI | `~/.codex/skills/` |
| Antigravity | `.agents/skills/` or `.agent/skills/` |
| Gemini CLI | auto-detected |

### 🔍 Browse on skills.sh

```
https://skills.sh/bmsuisse/skills/<skill-name>
```

> Skills appear on the [skills.sh leaderboard](https://skills.sh) automatically based on install telemetry — no manual registration required.

### ✅ Verify installation

Start a new session and ask your agent something that should trigger the skill.

---

## 🛠️ Adding a Skill

Use **skill-creator** to guide you through the full lifecycle — drafting, test cases, evaluation, and iteration:

```bash
npx skills add https://github.com/anthropics/skills --skill skill-creator
```

Then ask your agent: *"Help me create a skill for X"* and it will walk you through intent capture, writing the `SKILL.md`, running test cases, reviewing results, and iterating until the skill is ready.

### Structure

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
3. Merge to `main` — CI auto-updates the **Available Skills** table above

---

## 🗂️ Repo Structure

```
.
├── skills/                   ← canonical skill sources
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── scripts/
│       └── references/
├── .agents/skills/           ← runtime: Antigravity (git-ignored)
├── .claude/skills/           ← runtime: Claude Code (git-ignored)
├── scripts/update_readme.py  ← auto-generates the skills table in README.md
└── .github/workflows/        ← CI: auto-updates README on push to main
```

> The `Available Skills` table is auto-generated by CI on every push to `main`. Never edit it manually.

---

## 🔄 Updating Third-Party Skills

```bash
npx skills update
```
