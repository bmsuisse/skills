---
name: prek
plugin: coding
description: >
  Set up code formatting and pre-commit hooks using prek (fast Rust-based
  alternative to pre-commit) with prek.toml config. Use whenever the user
  wants to configure prek, add formatters, set up pre-commit hooks, or enforce
  code style. Triggers on "set up prek", "add formatting", "configure
  formatters", "pre-commit setup", "add ruff", "set up prettier",
  "configure sqlfmt". Works on new and existing projects. Always use when
  init-app-stack has just run.
---

# Prek — Pre-commit Formatter Setup

[prek](https://prek.j178.dev/) is a fast, Rust-native drop-in alternative to
pre-commit. It reads `prek.toml` and runs formatters automatically on staged
files at commit time.

**Formatters — all use 4 spaces, no tabs, line-length 120:**
- **Python**: ruff-check --fix + ruff-format (via astral-sh/ruff-pre-commit)
- **SQL**: `uv run sqlfmt` (local hook)
- **TypeScript/JS**: `bunx --bun prettier --write` (local hook)
- **YAML**: builtin check-yaml (if .yaml/.yml files present)

---

## Step 0: Ensure prek is installed

```bash
prek --version
```

If not installed, the simplest install for this stack is:

```bash
uv tool install prek
```

Other options: `brew install prek`, `winget install --id j178.Prek`, or download
binary from https://github.com/j178/prek/releases.

---

## Step 1: Detect file types in the project

```bash
find . -name "*.py"  -not -path "./.git/*" -not -path "./node_modules/*" | head -1
find . -name "*.sql" -not -path "./.git/*" | head -1
find . \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \) \
  -not -path "./.git/*" -not -path "./node_modules/*" | head -1
find . \( -name "*.yaml" -o -name "*.yml" \) -not -path "./.git/*" | head -1
```

Include a repo/hook only when matching files exist. On a freshly scaffolded
project with no files yet, use the declared stack to decide.

---

## Step 2: Write prek.toml

Write `prek.toml` to the project root. The structure mirrors pre-commit's
`[[repos]]` / hooks model — each `[[repos]]` block is a hook source.

```toml
# prek.toml — pre-commit formatter configuration
# Install git hook: prek install
# Format all files: prek run --all-files

[[repos]]                                 # include only if .yaml/.yml present
repo = "builtin"
hooks = [
    { id = "check-yaml" },
]

[[repos]]                                 # include only if .py files present
repo = "https://github.com/astral-sh/ruff-pre-commit"
rev = "v0.11.0"                           # verify: https://github.com/astral-sh/ruff-pre-commit/releases
hooks = [
    { id = "ruff-check", args = ["--fix"] },
    { id = "ruff-format" },
]

[[repos]]                                 # include only if .sql files present
repo = "local"
hooks = [
    { id = "sqlfmt", name = "sqlfmt", language = "system", entry = "uv run sqlfmt", files = '\\.sql$' },
]

[[repos]]                                 # include only if .ts/.tsx/.js/.jsx present
repo = "local"
hooks = [
    { id = "prettier", name = "prettier", language = "system", entry = "bunx --bun prettier --write", files = '\\.(ts|tsx|js|jsx|vue)$' },
]
```

**Tip on ruff rev**: run `uv run ruff --version` in the project to see the
installed version, then use the matching tag from the ruff-pre-commit releases.

---

## Step 3: Update pyproject.toml

If `pyproject.toml` exists or Python files are present, add/merge these
sections. Don't overwrite keys the user already set:

```toml
[tool.ruff]
line-length = 120
indent-width = 4
target-version = "py313"

[tool.ruff.format]
indent-style = "space"
quote-style = "double"
line-ending = "auto"

[tool.sqlfmt]
line_length = 120
```

---

## Step 4: Write .prettierrc

If TypeScript/JavaScript files are present, write `.prettierrc` to the project
root (skip if one already exists with different settings — ask first):

```json
{
  "tabWidth": 4,
  "useTabs": false,
  "semi": true,
  "singleQuote": false,
  "printWidth": 120,
  "trailingComma": "es5"
}
```

---

## Step 5: Install the git hook

```bash
prek install
```

This writes `.git/hooks/pre-commit` automatically — no manual hook file needed.

---

## Step 6: Run formatters on all existing files

```bash
prek run --all-files
```

If a tool is missing (prek not found, uv not installed, bunx not available),
report it clearly and suggest the install command. Don't fail silently.

---

## After setup — tell the user

- Which hooks were installed and why (based on detected file types)
- `prek run --all-files` runs all hooks manually on every file
- The git hook fires automatically on `git commit`
- What was added/merged into `pyproject.toml`
