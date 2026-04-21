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

## Available Skills

<!-- SKILLS_TABLE_START -->
| Skill | Description |
|---|---|
| [autoresearch](./skills/autoresearch/) | Autonomous iterative experimentation loop for Python, SQL, ML, and Spark/Databricks projects. Guides you through defi… |
| [bms](./skills/bms/) | Master skill for the bmsuisse platform — routes to the relevant skills based on sub-command. Always enables caveman c… |
| [codeunit-analyzer](./skills/codeunit-analyzer/) | Comprehensive C-AL performance analyzer for Classic Microsoft Dynamics NAV (Navision). Targets Classic NAV anti-patte… |
| [coding-guidelines-python](./skills/coding-guidelines-python/) | Apply and enforce Python-specific coding standards. Use alongside coding-guidelines for any Python file — covers typi… |
| [coding-guidelines-sql](./skills/coding-guidelines-sql/) | SQL and data warehouse coding guidelines for the BME data platform. Use this skill whenever the user is writing, revi… |
| [coding-guidelines-typescript](./skills/coding-guidelines-typescript/) | Apply and enforce TypeScript-specific coding standards. Use alongside coding-guidelines for any TypeScript file — cov… |
| [data-modeling-dimensional](./skills/data-modeling-dimensional/) | Dimensional data modeling guide for the Fabricks platform — covers the full pipeline from staging through raw, transf… |
| [databricks-cli](./skills/databricks-cli/) | Databricks CLI operations: auth, profiles, data exploration, bundles, and notebook execution. Use this skill for ANY… |
| [databricks-sql-autotuner](./skills/databricks-sql-autotuner/) | Databricks SQL query optimizer and error fixer: analyzes a slow or broken SQL query, rewrites it for speed using SQL-… |
| [deslop](./skills/deslop/) | Remove AI slop from code and pull requests. Use this skill whenever the user wants to clean up AI-generated code, rev… |
| [duckdb](./skills/duckdb/) | Guide for working with DuckDB — CLI usage, SQL execution, reading files (CSV, Parquet, JSON, Excel), extensions (http… |
| [fabricks-glossary](./skills/fabricks-glossary/) | Use this skill whenever company-specific jargon, acronyms, or domain terminology is needed to answer correctly. |
| [fabricks-sql-analyzer](./skills/fabricks-sql-analyzer/) | Analyzes all SQL files in the Fabricks.Runtime repository, builds a dependency DAG, runs performance heuristics, and… |
| [fastapi-azure-auth](./skills/fastapi-azure-auth/) | Azure Entra ID SSO for FastAPI using cookie-based sessions (MSAL, /login → /callback → session). Trigger on: Azure AD… |
| [fastapi-guideline](./skills/fastapi-guideline/) | Use this skill whenever working with FastAPI — building APIs, adding routes, structuring projects, streaming response… |
| [init-app-stack](./skills/init-app-stack/) | Use this skill whenever the user wants to bootstrap, scaffold, or initialize a new full-stack app with a Vite + React… |
| [kendo-ui-angular](./skills/kendo-ui-angular/) | Use this skill whenever the user is working with Kendo UI for Angular — including the Data Grid, TreeList, TreeView,… |
| [kendo-ui-react](./skills/kendo-ui-react/) | KendoReact component library patterns and best practices for React developers. Trigger whenever the user works with K… |
| [kendo-ui-vue](./skills/kendo-ui-vue/) | Use this skill whenever the user is working with Kendo UI for Vue — including the Data Grid, DropDownList, ComboBox,… |
| [nicegui](./skills/nicegui/) | Build Python web UIs with NiceGUI — covering layout, widgets, data binding, routing, and the AgGrid data grid. Use th… |
| [postgres-best-practices](./skills/postgres-best-practices/) | PostgreSQL coding standards for Python projects using psycopg (no ORM). Use this skill whenever the user is writing o… |
| [postgres-test-setup](./skills/postgres-test-setup/) | Set up and work with a local PostgreSQL test database in Docker for integration/e2e tests. Use this skill whenever th… |
| [python-autotuner](./skills/python-autotuner/) | Python code optimizer and error fixer: analyzes a Python file or function, rewrites it for speed and quality using on… |
| [remove-ai-writing](./skills/remove-ai-writing/) | "Detect and surgically fix AI writing patterns in English, German, French, or Italian text. Use this skill whenever t… |
| [scientific-revision](./skills/scientific-revision/) | Use this skill whenever the user wants to verify, revise, or improve a scientific essay, academic paper, or any writt… |
| [spark-connect](./skills/spark-connect/) | Guide for running PySpark code locally against a remote Databricks cluster via Spark Connect (databricks-connect). Us… |
| [sql-optimization](./skills/sql-optimization/) | "Universal SQL performance optimization assistant for comprehensive query tuning, indexing strategies, and database p… |
| [tanstack-best-practices](./skills/tanstack-best-practices/) | Comprehensive best practices for TanStack libraries in React applications — covering TanStack Query (React Query) dat… |
<!-- SKILLS_TABLE_END -->

---

## Installation

### Claude Code Plugin

Add to `~/.claude/settings.json` to install all plugins:

```json
{
  "extraKnownMarketplaces": {
    "bmsuisse-skills": {
      "source": {
        "source": "github",
        "repo": "bmsuisse/skills",
        "ref": "main"
      }
    }
  },
  "enabledPlugins": {
    "coding@bmsuisse-skills": true,
    "onetrade@bmsuisse-skills": true,
    "databricks@bmsuisse-skills": true,
    "fabricks-data@bmsuisse-skills": true,
    "writing@bmsuisse-skills": true,
    "ui@bmsuisse-skills": true,
    "caveman@bmsuisse-skills": true,
    "azure-deploy@bmsuisse-skills": true,
    "azure-diagnostics@bmsuisse-skills": true
  }
}
```

| Plugin                             | Contents                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------- |
| `coding@bmsuisse-skills`           | Python, TypeScript, FastAPI, Postgres, TanStack, and general coding skills |
| `ui@bmsuisse-skills`               | KendoReact component patterns and best practices                          |
| `onetrade@bmsuisse-skills`         | C-AL / Classic NAV codeunit analysis                                      |
| `databricks@bmsuisse-skills`       | Databricks CLI + Spark Connect local execution                            |
| `fabricks-data@bmsuisse-skills`    | Fabricks / Databricks data skills                                         |
| `writing@bmsuisse-skills`          | Scientific and academic writing revision                                  |
| `caveman@bmsuisse-skills`          | Ultra-compressed caveman communication mode (~75% token reduction)        |
| `azure-deploy@bmsuisse-skills`     | Azure deployments via azd/terraform/az with validation and RBAC checks    |
| `azure-diagnostics@bmsuisse-skills`| Azure production diagnostics via AppLens, Monitor, and resource health    |

Then run these commands in Claude Code to apply the configuration:

```bash
# Add the marketplace (one-time setup — alternative to editing settings.json manually)
/plugin marketplace add bmsuisse/skills

# Install the plugins you want
/plugin install coding@bmsuisse-skills
/plugin install onetrade@bmsuisse-skills
/plugin install fabricks-data@bmsuisse-skills
/plugin install writing@bmsuisse-skills

# After any config change, reload without restarting
/reload-plugins
```

| Command                                    | Description                                                           |
| ------------------------------------------ | --------------------------------------------------------------------- |
| `/plugin`                                  | Open the interactive plugin manager (browse, install, enable/disable) |
| `/plugin install <name>@bmsuisse-skills`   | Install a specific plugin                                             |
| `/plugin uninstall <name>@bmsuisse-skills` | Remove a plugin                                                       |
| `/plugin enable <name>@bmsuisse-skills`    | Re-enable a disabled plugin                                           |
| `/plugin disable <name>@bmsuisse-skills`   | Disable without uninstalling                                          |
| `/reload-plugins`                          | Reload all active plugins without restarting Claude Code              |

### Using the Plugin

Once installed, skills are available as **slash commands** in Claude Code. Type `/` to see all available commands, or invoke them directly:

```
/coding-guidelines-python      # activate Python coding standards
/fastapi-guideline             # load FastAPI best practices
/init-app-stack                # scaffold a Vite+React+TanStack+shadcn / FastAPI+asyncpg app
/databricks-cli                # Databricks CLI operations
/autoresearch                  # start an autonomous research loop
/deslop                        # clean AI slop from code or PRs
```

Skills also **auto-trigger** based on context — if a skill's description matches what you're doing, Claude Code may load it automatically without a slash command.

#### Hooks (automatic tool remapping)

The plugin ships with **PreToolUse hooks** that automatically rewrite shell commands to use preferred tooling:

| You type                    | Gets remapped to                    |
| --------------------------- | ----------------------------------- |
| `python script.py`          | `uv run python script.py`           |
| `python -m pytest`          | `uv run -m pytest`                  |
| `pip install foo`           | `uv add foo`                        |
| `pytest`, `ruff`, `ty` | `uv run pytest`, `uv run ruff`, ... |
| `npm install`               | `bun install`                       |
| `npm install foo`           | `bun add foo`                       |
| `npx foo`                   | `bunx foo`                          |
| `yarn add foo`              | `bun add foo`                       |
| `pnpm run dev`              | `bun run dev`                       |

This happens transparently — no config needed. The hooks activate for any plugin that includes them (`coding`, `bms`, etc.).

#### Plugin contents

Each plugin bundles a curated set of skills:

| Plugin             | Skills included                                                                                                                                                                              | Use case                          |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `coding`           | autoresearch, coding-guidelines-python, coding-guidelines-typescript, deslop, fastapi-guideline, init-app-stack, postgres-best-practices, postgres-test-setup, sql-optimization, tanstack-best-practices | General dev work         |
| `ui`               | kendo-ui-react                                                                                                                                                                               | KendoReact components             |
| `onetrade`         | codeunit-analyzer                                                                                                                                                                            | Classic NAV / C-AL analysis       |
| `databricks`       | databricks-cli, spark-connect                                                                                                                                                                | Databricks & Spark                |
| `fabricks-data`    | fabricks-glossary, fabricks-sql-analyzer                                                                                                                                                     | Fabricks data platform            |
| `writing`          | remove-ai-writing, scientific-revision                                                                                                                                                       | Writing & docs                    |
| `bms`              | bms (master), coding-guidelines-sql, coding-guidelines-python, coding-guidelines-typescript, sql-optimization, data-modeling-dimensional, fabricks-glossary                                  | All BMSuisse standards via `/bms` |
| `caveman`          | caveman, caveman-review, caveman-commit, caveman-help *(from JuliusBrussee/caveman)*                                                                                                         | Token-efficient communication     |
| `azure-deploy`     | azure-deploy *(from microsoft/azure-skills)*                                                                                                                                                 | Azure deployments                 |
| `azure-diagnostics`| azure-diagnostics *(from microsoft/azure-skills)*                                                                                                                                           | Azure production diagnostics      |

---

### Highly recommended: Caveman mode

We highly recommend **[Caveman](https://github.com/JuliusBrussee/caveman)** by **[Julius Brussee](https://github.com/JuliusBrussee)**. It cuts token usage ~75% by having the agent respond in ultra-compressed style while keeping full technical accuracy. Less noise, faster, cheaper.

```bash
bun x skills add https://github.com/JuliusBrussee/caveman
```

Or via the marketplace:

```json
"caveman@bmsuisse-skills": true
```

Full credit to Julius for creating and maintaining this — outstanding contribution to the community.

---

### skills CLI

The `skills` CLI reads directly from GitHub — no registration needed.

### Install a specific skill

```bash
# recommended
bun x skills add https://github.com/bmsuisse/skills --skill <skill-name>
# alternative
npx skills add https://github.com/bmsuisse/skills --skill <skill-name>
```

### Install all skills

```bash
# recommended
bun x skills add https://github.com/bmsuisse/skills
# alternative
npx skills add https://github.com/bmsuisse/skills
```

The CLI auto-detects your agent platform and installs into the right directory:

| Platform    | Directory                             |
| ----------- | ------------------------------------- |
| Claude Code | `.claude/skills/`                     |
| Cursor      | `.cursor/rules/`                      |
| Codex CLI   | `~/.codex/skills/`                    |
| Antigravity | `.agents/skills/` or `.agent/skills/` |
| Gemini CLI  | auto-detected                         |

### Browse on skills.sh

```
https://skills.sh/bmsuisse/skills/<skill-name>
```

> Skills appear on the [skills.sh leaderboard](https://skills.sh) automatically based on install telemetry — no manual registration required.

### Verify installation

Start a new session and ask your agent something that should trigger the skill.

---

## BMS Master Skill

`/bms` is a master skill that activates the full bmsuisse coding context in one command. It routes to the relevant sub-skills based on a sub-command and always enables caveman communication style.

### Sub-commands

| Command       | Loads                                                                                               | Good for                                    |
| ------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `/bms`        | coding-guidelines-sql · coding-guidelines-python · coding-guidelines-typescript · fabricks-glossary | General session — all core standards active |
| `/bms sql`    | coding-guidelines-sql · sql-optimization · fabricks-glossary                                        | SQL authoring, reviews, refactoring         |
| `/bms python` | coding-guidelines-python                                                                            | Python development, PR reviews              |
| `/bms data`   | data-modeling-dimensional · fabricks-glossary                                                       | Designing or reviewing fact/dim tables      |

For deep optimization work, chain with the specialized skills:

- SQL benchmarking → `/databricks-sql-autotuner`
- Python benchmarking → `/python-autotuner`

### How it works

```
/bms sql
  │
  ├─ reads bms/SKILL.md          (master router, ~2.5k chars)
  │
  ├─ runs load_skills.py sql     (helper script)
  │     └─ concatenates:
  │           coding-guidelines-sql/SKILL.md
  │           sql-optimization/SKILL.md
  │           fabricks-glossary/SKILL.md
  │
  └─ applies all rules + caveman mode → "BMS SQL active."
```

The helper script at `skills/bms/scripts/load_skills.py` concatenates the relevant `SKILL.md` files and prints them as combined content. Each sub-skill remains the single source of truth — no duplication.

### Install

**Plugin (recommended)** — installs bms + all sub-skills as a self-contained plugin:

```bash
claude plugin marketplace add bmsuisse/skills
claude plugin install bms@bmsuisse-skills
```

**skills CLI** — installs the bms skill only (sub-skills must already be installed):

```bash
bun x skills add https://github.com/bmsuisse/skills --skill bms  # recommended
npx  skills add https://github.com/bmsuisse/skills --skill bms  # alternative
```

### Plugin path resolution

When installed as a plugin, `load_skills.py` resolves sub-skill paths via the `CLAUDE_PLUGIN_ROOT` environment variable that Claude Code injects at runtime. In the repo, it falls back to the repo-relative path. This means the script works correctly in both contexts without configuration.

---

## Adding a Skill

Use **skill-creator** to guide you through the full lifecycle — drafting, test cases, evaluation, and iteration:

```bash
bun x skills add https://github.com/anthropics/skills --skill skill-creator  # recommended
# npx skills add https://github.com/anthropics/skills --skill skill-creator
```

Then ask your agent: _"Help me create a skill for X"_ and it will walk you through intent capture, writing the `SKILL.md`, running test cases, reviewing results, and iterating until the skill is ready.

Also helpful is the playwright-cli skill, which you can install like this:

```bash
bun install -g @playwright/cli@latest
bunx playwright-cli install --skills
```

You can give a hint to the agent to use playwright cli to query complex web pages with javascript.

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

## Repo Structure

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

## Updating Third-Party Skills

```bash
bun x skills update  # recommended / npx skills update
```
