# Ruff setup for Python repos (BMS baseline)

Clean code that depends on reviewers noticing is clean code that decays. This
is the ruff configuration OneSales runs (`pyproject.toml`), recommended as the
baseline for every BMS Python repo. Hooks and CI wiring live in the `prek`
skill; this file is the rule set.

## Contents

- Recommended config
- Why these rules
- Rules for suppressions
- Adopting it in an existing repo
- Complexity and dead-code checks
- Enforcement

## Recommended config

```toml
[tool.ruff]
line-length = 120
indent-width = 4
target-version = "py314"          # match requires-python / .python-version
extend-exclude = ["*.md"]         # ruff 0.16 also lints Python blocks in Markdown; add submodules here

[tool.ruff.lint]
# Explicit select: ruff 0.16 widened the default rule set, so never rely on it.
select = [
    "E", "F", "I",   # pycodestyle, pyflakes, isort
    "UP",            # pyupgrade: X | None, modern syntax
    "B",             # bugbear: mutable defaults etc.
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
    "FAST",          # FastAPI: Annotated[...] dependencies (drop if no FastAPI)
]
ignore = ["ANN401"]  # `Any` is surfaced as a warning by a separate non-blocking hook

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.lint.flake8-tidy-imports.banned-api]
# Project decisions as lint errors, so reviewers don't repeat them. Examples from OneSales:
"sqlalchemy".msg = "No ORM - use pgdevkit (psycopg)."
"uvicorn".msg = "Granian is the server."

[tool.ruff.lint.per-file-ignores]
# print() is the output channel of CLI scripts
"scripts/**" = ["T20"]

[tool.ruff.format]
indent-style = "space"
quote-style = "double"
line-ending = "auto"
```

`banned-api` entries are project-specific; replace them with the repo's own
decisions (or drop the table).

## Why these rules

Each group maps to a clean-code principle, which is why this is the baseline:

| Rules | Enforces |
|-------|----------|
| `F`, `E`, `I`, `UP` | No unused imports/variables, consistent imports, modern syntax |
| `B`, `PLE`, `PLW`, `ASYNC`, `DTZ` | Bug magnets: mutable defaults, blocking calls in async, naive datetimes |
| `SIM`, `C4`, `PERF`, `FURB`, `PIE`, `RET`, `FLY` | Simpler control flow and fewer needless constructs |
| `N`, `A` | Naming: PEP 8, no shadowed builtins |
| `ANN` | Typed interfaces (the interface is the contract) |
| `TID` | Absolute imports only; banned APIs encode architecture decisions |
| `T20`, `LOG` | No stray `print()`, correct logging |
| `PTH` | `pathlib` over `os.path` |

## Rules for suppressions

- Suppress with a targeted `# noqa: CODE  # reason`. No blanket `# noqa`, no
  file-level ignores without a comment explaining why.
- Prefer `per-file-ignores` with a comment for a whole file that legitimately
  differs (CLI scripts, generated wire-format models).
- A rule that fires constantly for a good reason belongs in `ignore` with a
  comment, not scattered across `noqa`s.

## Adopting it in an existing repo

1. Add the config, then run `uv run ruff check --statistics` to see which rules
   fire how often. Don't turn 4,000 violations into one giant PR.
2. Enable the auto-fixable rules first (`ruff check --fix`; `I`, `UP`, `F401`,
   `C4`, `SIM`) in their own commit, separate from behaviour changes.
3. For rules with many manual fixes (`ANN`, `N`, `PTH`), start with
   `per-file-ignores` for the legacy paths and shrink that list over time, or
   add the rule family when the module is next touched.
4. Make it blocking only once the repo is green, so the gate is trusted.

## Complexity and dead-code checks

Not in the blocking rule set; run on demand, as OneSales does in its `justfile`:

```sh
# Functions over the complexity threshold (C901, default max 10)
ruff check --select C901 --config "lint.mccabe.max-complexity=10" <src>
# Unused imports / locals / arguments (also part of the dead-code-audit skill)
ruff check --select F401,F841,ARG --no-fix <src>
```

Complex functions are the first candidates for splitting (see "Functions" in
the main skill). For unused code across the repo, use `dead-code-audit`.

## Enforcement

Three layers, cheapest first, same config in all of them:

1. **Claude hook**: lint every file Claude edits and send what is left back to
   it, so it fixes violations immediately instead of at the pre-push gate. Copy
   `hooks/lint_on_edit.py` from this skill into the repo (e.g. `.claude/hooks/`) and add
   to `.claude/settings.json`:

   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Edit|Write",
           "hooks": [{ "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/lint_on_edit.py\"" }]
         }
       ]
     }
   }
   ```

   It runs `ruff check --fix` on `.py` files (and `biome check --write` on
   TS/JS/Vue when a `biome.json` exists), fixes what it can silently, and exits
   2 with the remaining violations on stderr so Claude sees them. It does nothing
   when the repo has no ruff/biome config or the tool is missing, and only blocks
   on real violations (ruff/biome exit 1), never on linter or config failures.
   Trust note: it runs the project's own `ruff`/`biome` (`.venv`, `node_modules`,
   `uv run`), so install it only in repos you trust, as with any hook or lint script. Avoid the
   common one-liner variant that ends in `2>/dev/null; true`: it discards the
   violations, so Claude never learns what is still broken.
2. **Pre-commit** via `prek` (`ruff-check --fix`, `ruff-format`, optionally a
   non-blocking `ruff check --select ANN401 --exit-zero` hook that only prints
   `Any` usage). See the `prek` skill for the exact hook entries.
3. **CI** runs `ruff check` and `ruff format --check`, so a skipped local hook
   can't merge.

Pair it with a type checker (`ty check`) and, for the frontend, Biome plus
`tsc`; see `coding-guidelines-typescript`.
