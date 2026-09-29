---
name: prek
plugin: coding
description: >
  Set up code formatting and pre-commit hooks using prek (fast Rust-based
  alternative to pre-commit) with prek.toml config. Use whenever the user
  wants to configure prek, add formatters, set up pre-commit hooks, or enforce
  code style. Triggers on "set up prek", "add formatting", "configure
  formatters", "pre-commit setup", "add ruff", "set up biome",
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
- **TypeScript/JS**: `bunx --bun biome check --write` (local hook, also lints
  and organizes imports)
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
rev = "v0.16.9"                           # verify: https://github.com/astral-sh/ruff-pre-commit/releases
hooks = [
    { id = "ruff-check", args = ["--fix"] },
    { id = "ruff-format" },
]

[[repos]]                                 # include only if .py files present — warning only, never blocks
repo = "local"
hooks = [
    { id = "ruff-warn-any", name = "ruff warn: typing.Any (ANN401)", language = "system", entry = "uv run ruff check --select ANN401 --exit-zero --output-format concise", types = ["python"], verbose = true },
]

[[repos]]                                 # include only if .sql files present
repo = "local"
hooks = [
    { id = "sqlfmt", name = "sqlfmt", language = "system", entry = "uv run sqlfmt", files = '\\.sql$' },
]

[[repos]]                                 # include only if .ts/.tsx/.js/.jsx present
repo = "local"
hooks = [
    { id = "biome", name = "biome", language = "system", entry = "bunx --bun biome check --write", files = '\\.(ts|tsx|js|jsx|vue)$' },
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

**Why ANN401 is a separate hook:** ruff has no warning severity — every
violation fails `ruff-check`. `ANN401` (`typing.Any`) is ignored in the lint
config and re-run by `ruff-warn-any` with `--exit-zero`, so it prints but never
blocks the commit. If the project uses FastAPI, uncomment `"FAST"` in `select`.

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
target-version = "py314"

[tool.ruff.lint]
select = [
    "E", "F", "I",   # pycodestyle, pyflakes, isort
    "UP",            # pyupgrade — X | None, modern syntax
    "B",             # bugbear — mutable defaults etc.
    "ANN",           # full type annotations
    "SIM", "C4",     # simplifiable code, needless comprehensions/casts
    "PERF", "FURB",  # needless loops, manual list/dict building
    "ASYNC",         # blocking calls inside async def
    "RUF",
    "N",             # PEP 8 naming
    "PTH",           # pathlib instead of os.path
    "TID",           # absolute imports only, banned APIs
    "RET", "PIE",    # consistent returns, misc simplifications
    "A",             # no shadowing builtins
    "T20",           # no print()  (per-file-ignore CLI scripts)
    "LOG",           # logging API misuse
    "DTZ",           # timezone-aware datetimes
    "FLY",           # f-string instead of str.join on literals
    "PLE", "PLW",    # pylint errors + warnings
    # "FAST",        # add only if the project uses FastAPI
]
ignore = ["ANN401"]  # `Any` is a warning via the ruff-warn-any hook, not an error

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.format]
indent-style = "space"
quote-style = "double"
line-ending = "auto"

[tool.sqlfmt]
line_length = 120
```

---

## Step 5: Write biome.json

If TypeScript/JavaScript files are present, write `biome.json` to the project
root (skip if one already exists with different settings — ask first). Also
add `@biomejs/biome` as a dev dependency (`bun add -d @biomejs/biome`) if not
already present:

```json
{
  "$schema": "https://biomejs.dev/schemas/2.5.11/schema.json",
  "vcs": { "enabled": true, "clientKind": "git", "useIgnoreFile": true },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 4,
    "lineWidth": 120
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "double",
      "semicolons": "always",
      "trailingCommas": "es5"
    }
  },
  "linter": { "enabled": true }
}
```

If the project already has an eslint config (`.eslintrc*` or
`eslint.config.*`), migrate it instead of hand-writing rules:

```bash
bunx @biomejs/biome migrate eslint --write
bunx @biomejs/biome migrate prettier --write
```

then remove the old `eslint`, `prettier`, and related plugin dependencies and
config files.

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
