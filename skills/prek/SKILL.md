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
- **File-size guard**: `scripts/check_files.py` (local hook, always included) — blocks
  commits containing files over a per-extension line-count limit, and (for `.sql`)
  forbidden join patterns. BMS convention, seen in mdmapp and OneSales.

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

## Step 2: Write scripts/check_files.py

Always write this file, regardless of detected file types — it's the file-size
and forbidden-pattern guard (mdmapp/OneSales convention), gated per-extension
by `LINE_LIMITS` so it's a no-op for extensions a project doesn't use.

```python
import pathlib
import re
import sys

# Regex to match forbidden patterns (case-insensitive)
# - RIGHT [OUTER] JOIN
# - [ANY] JOIN LATERAL or LATERAL [OUTER] JOIN
# - CROSS APPLY
FORBIDDEN_SQL_PATTERN = re.compile(
    r"(?i)(RIGHT\s+(OUTER\s+)?JOIN|JOIN\s+LATERAL|LATERAL\s+(OUTER\s+)?JOIN|CROSS\s+APPLY)"
)

# Line limits per file extension
LINE_LIMITS = {
    ".py": 1200,
    ".ts": 600,
    ".tsx": 900,
    ".vue": 900,
    ".sql": 1200,
    ".sh": 100,
    ".md": 1000,
}


def main():
    files = sys.argv[1:]
    if not files:
        return

    failed = False
    for file_path in files:
        path = pathlib.Path(file_path)
        if not path.is_file():
            continue

        # Ignore lock files and auto-generated code (e.g. openapi-ts output under lib/generated/)
        if (
            path.suffix == ".lock"
            or path.name.endswith(".lock.json")
            or ".generated." in path.name
            or ".gen." in path.name
            or "generated" in path.parts
        ):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Skip binary files or files with unknown encoding
            continue

        lines = content.splitlines()
        line_count = len(lines)
        extension = path.suffix

        # 1. Check for forbidden SQL patterns
        if extension == ".sql":
            matches = list(FORBIDDEN_SQL_PATTERN.finditer(content))
            if matches:
                failed = True
                print(f"Error: Forbidden SQL pattern found in {file_path}:")
                for match in matches:
                    line_no = content.count("\n", 0, match.start()) + 1
                    print(f"  Line {line_no}: '{match.group(0)}'")
                print("-" * 40)

        # 2. Check line count limits
        if extension in LINE_LIMITS:
            limit = int(LINE_LIMITS[extension])
            if path.name.upper() == "AGENTS.MD":
                limit = 1000  # Special case for AGENTS.MD
            if path.name.startswith("test_") and extension in [".py", ".ts"]:
                # Allow 50% more lines for test files
                limit = int(limit * 1.5)
            if path.name.endswith(".py") and line_count < limit and line_count > 600:
                print(f"Warning: {file_path} has {line_count} lines, which is above 600. Consider refactoring.")
            if line_count > limit:
                failed = True
                print(f"Error: File {file_path} too long ({line_count} lines, limit is {limit} for {extension})")
                print("-" * 40)

    if failed:
        print("Refactor these files into smaller, nicely structured code, even if error was preexisting.")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
```

Adjust `LINE_LIMITS` only if the user asks for different thresholds — don't
silently loosen them because a specific file is already over the limit.

---

## Step 3: Write prek.toml

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

[[repos]]                                 # always include — file-size + forbidden-pattern guard
repo = "local"
hooks = [
    { id = "check-files", name = "Check File Quality", language = "system", entry = "uv run python scripts/check_files.py", types_or = [
        "sql",
        "python",
        "ts",
        "vue",
        "shell",
        "markdown",
    ] },
]
```

**Tip on ruff rev**: run `uv run ruff --version` in the project to see the
installed version, then use the matching tag from the ruff-pre-commit releases.

---

## Step 4: Update pyproject.toml

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

## Step 5: Write .prettierrc

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

## Step 6: Install the git hook

```bash
prek install
```

This writes `.git/hooks/pre-commit` automatically — no manual hook file needed.

---

## Step 7: Run formatters on all existing files

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
