---
name: python-autotuner
description: >
  Python code optimizer and error fixer: analyzes a Python file or function,
  rewrites it for speed and quality one change at a time, validates with pytest,
  benchmarks with timeit, checks with ruff/ty, and measures complexity reduction.
  Also diagnoses broken Python code (SyntaxError, ImportError, TypeError,
  AttributeError, runtime crashes) using --goals fix.
  Trigger on: "/python-autotuner", "optimize this Python", "make this function
  faster", "benchmark my Python function", "reduce complexity", "ruff keeps
  failing", "my Python function is too slow", "simplify this Python code",
  "fix this Python error", "SyntaxError in Python", "my Python code is crashing",
  "TypeError in Python", or whenever a user shares Python code and mentions
  errors, crashes, performance, quality, slowness, or complexity.
compatibility: Requires Python 3.10+, uv. ruff/ty/pytest/pytest-benchmark installed via uv if missing.
---

# Python Autotuner

Analyze, rewrite, validate, and benchmark Python code locally. Each rewrite
attempt must pass all existing tests before it is accepted. Speed improvements
must be statistically meaningful. Quality improvements must reduce ruff
violations, ty errors, or complexity score.

## Examples

```
# Optimize a file with default goals (speed + quality)
/python-autotuner mymodule/processor.py

# Target a specific function, 5 benchmark runs
/python-autotuner --function parse_records --n-runs 5 mymodule/parser.py

# Quality only (no benchmarking — fast path)
/python-autotuner --goals quality mymodule/utils.py

# Simplify only
/python-autotuner --goals simplicity mymodule/complex_logic.py

# All goals
/python-autotuner --goals speed,quality,simplicity mymodule/data.py

# Audit only — analyze and print attack plan, make no changes
/python-autotuner --explain-only mymodule/processor.py

# Fix a broken file (SyntaxError, ImportError, TypeError, runtime crash)
/python-autotuner --goals fix mymodule/broken_parser.py
```

---

## Scripts

| Script | Purpose |
|:-------|:--------|
| `scripts/complexity.py` | AST-based complexity score (LOC + nesting + cyclomatic). Lower = simpler. |
| `scripts/benchmark.py` | Time functions via `timeit` using a `benchmark_spec.py` spec file. No pytest-benchmark fixtures needed. Outputs mean/std/CI per function and before/after speedup. |
| `scripts/check_quality.py` | Run ruff + ty, return structured JSON (violations, errors, counts) |

Read each script before using it — they accept `--json` for machine-readable output.

---

## Phase 0 — Parse input

The user invokes with:

```
/python-autotuner [options] <file>
```

| Option | Example | Default | Effect |
|:-------|:--------|:--------|:-------|
| `--function <name>` | `--function parse_records` | all functions | Focus benchmark and profiling on a specific function |
| `--goals <list>` | `--goals speed,quality` | `speed,quality` | Comma-separated: `speed`, `quality`, `simplicity`, `fix` |
| `--n-runs <n>` | `--n-runs 5` | `3` | Benchmark runs per variant (only used when goals include `speed`) |
| `--test-file <path>` | `--test-file tests/test_parser.py` | auto-discover | pytest file to use for validation |
| `--explain-only` | `--explain-only` | off | Run Phases 0–3 only: analyze and print attack plan, then stop. No edits made. |

Record as `TARGET_FILE`, `TARGET_FUNCTION` (or None), `GOALS`, `N_RUNS`, `TEST_FILE`, `EXPLAIN_ONLY`.

**Goal-gating — skip work that doesn't apply:**

| Goals active | Skip |
|:-------------|:-----|
| `quality` only | Phases 2.3, 3.3 (no benchmark or profiling needed) |
| `simplicity` only | Phases 2.3, 3.1, 3.2, 3.3 (no benchmark, ruff, or ty needed) |
| `speed` only | Phases 3.1, 3.2 (no ruff/ty analysis needed) |
| `fix` | Phases 2.3–2.5, 3.3–3.5 (no benchmarking, no loop — diagnose, patch, verify, done) |
| any | Phase 2.4 if ruff not in goals; Phase 2.5 if simplicity not in goals |

This avoids expensive benchmark runs when the user only wants quality, simplicity, or error fixes.

**Goal meanings:**

| Goal | What improves |
|:-----|:-------------|
| `speed` | timeit mean time (lower is better) |
| `quality` | ruff violation count + ty error count (lower is better) |
| `simplicity` | complexity score: LOC + nesting_depth×10 + cyclomatic×5 (lower is better) |
| `fix` | Broken code that errors at import or runtime. Success = code runs and tests pass. |

When `--goals` is omitted, default to `speed,quality`.

---

## Phase 1 — Environment check

Check that required tools exist. Install missing ones via uv.

```bash
# Check Python
python3 --version

# Check uv
uv --version || curl -LsSf https://astral.sh/uv/install.sh | sh

# Check / install tools
uv tool install ruff 2>/dev/null || true
uv tool install ty 2>/dev/null || true
uv pip install pytest pytest-benchmark 2>/dev/null || pip install pytest pytest-benchmark
```

Verify by running:
```bash
ruff --version
ty --version
pytest --version
python3 -c "import pytest_benchmark; print('pytest-benchmark ok')"
```

If any tool fails after install attempt, tell the user exactly what failed and stop.

---

## Phase 2 — Baseline

Run all checks on the **original unmodified file**. Record everything as the baseline.

### 2.1 Find tests

Auto-discover the test file if `--test-file` not given:
```bash
# Look for: tests/test_<stem>.py, test_<stem>.py, tests/<stem>_test.py
python3 -c "
from pathlib import Path
import sys
stem = Path(sys.argv[1]).stem
candidates = [
    Path('tests') / f'test_{stem}.py',
    Path(f'test_{stem}.py'),
    Path('tests') / f'{stem}_test.py',
]
for c in candidates:
    if c.exists():
        print(c); sys.exit(0)
print('NOT_FOUND')
" "$TARGET_FILE"
```

If no test file found: ask the user to provide one. Tests are required — the skill cannot validate rewrites without them.

### 2.2 Run baseline pytest

```bash
pytest "$TEST_FILE" -v 2>&1
```

**If tests fail at baseline:** stop and tell the user. Do not attempt optimization on broken code.

### 2.3 Run baseline benchmark *(skip if goals do not include `speed`)*

The benchmark script uses `timeit` directly — **no pytest-benchmark fixtures needed**.
It requires a `benchmark_spec.py` file next to the target. Check if one exists:

```bash
ls "$(dirname $TARGET_FILE)/benchmark_spec.py" 2>/dev/null && echo "found" || echo "missing"
```

**If missing:** create `benchmark_spec.py` next to the target file. Import the functions
and define realistic sample inputs based on what you see in the test file:

```python
# benchmark_spec.py — created by python-autotuner
from <module_stem> import fn1, fn2   # import from TARGET_FILE's module name

# Use realistic inputs — look at the test file for good sample data
_LARGE_INPUT = list(range(10_000))   # match the scale tests use
_TEXT = " ".join(["word"] * 500 + ["other"] * 200)

BENCHMARKS = {
    "fn1": lambda: fn1(_LARGE_INPUT),
    "fn2": lambda: fn2(_TEXT),
}
```

Keep the spec file committed — it stays useful across multiple optimization attempts.

Then run:

```bash
python3 "$SKILL_DIR/scripts/benchmark.py" \
  --file "$TARGET_FILE" \
  [--function "$TARGET_FUNCTION"] \
  --n-runs "$N_RUNS" \
  --json
```

Record: `baseline_mean_ms`, `baseline_std_ms`, `ci_low_ms`, `ci_high_ms` per benchmark.
Save output to `baseline_benchmark.json`.

### 2.4 Run baseline quality *(skip if goals do not include `quality`)*

```bash
python3 "$SKILL_DIR/scripts/check_quality.py" \
  --file "$TARGET_FILE" \
  --json
```

Record: `baseline_ruff_count`, `baseline_ty_count`.

### 2.5 Run baseline complexity *(skip if goals do not include `simplicity`)*

Use `radon` if available (more accurate), otherwise fall back to the bundled script:

```bash
# Preferred: radon cc (cyclomatic complexity per function)
radon cc "$TARGET_FILE" -s -j 2>/dev/null || \
  python3 "$SKILL_DIR/scripts/complexity.py" --file "$TARGET_FILE" --json
```

Record: `baseline_complexity_score`, `baseline_loc`, `baseline_max_nesting`, `baseline_cyclomatic`.

To install radon if missing: `uv tool install radon`.

### 2.6 Branch + backup

```bash
# Create a git branch for the tuning run
BRANCH="py-tune/$(basename $TARGET_FILE .py)-$(date +%Y%m%d-%H%M%S)"
git checkout -b "$BRANCH" 2>/dev/null || true

# Record original file for reverting failed attempts
ORIGINAL_BACKUP=$(mktemp /tmp/python-autotuner-original-XXXXX.py)
cp "$TARGET_FILE" "$ORIGINAL_BACKUP"
```

Print the baseline summary and wait for user confirmation before starting the loop. Only show sections relevant to active goals:

```
Baseline summary
────────────────
File:        <TARGET_FILE>
Tests:       <TEST_FILE> — <N> passed
Branch:      <BRANCH>
Goals:       <GOALS>

[if speed in goals]
Benchmark:   <mean_ms>ms ± <std_ms>ms  (<N_RUNS> runs)

[if quality in goals]
Ruff:        <baseline_ruff_count> violations
ty:          <baseline_ty_count> errors

[if simplicity in goals]
Complexity:  <baseline_complexity_score>
  LOC:         <baseline_loc>
  Nesting:     <baseline_max_nesting>
  Cyclomatic:  <baseline_cyclomatic>
```

If `--explain-only` was passed: print this summary, then jump straight to Phase 3 (analysis + attack plan) and **stop after Phase 3.5**. Do not edit any files.

Otherwise: > **Continue with optimization? (yes/no)**

---

## Phase 3 — Analysis

Identify what to improve before writing any code.

### 3.1 Read ruff output

```bash
ruff check "$TARGET_FILE" --output-format=json
```

Group violations by rule code. Note the most frequent and highest-severity ones.

### 3.2 Read ty output

```bash
ty check "$TARGET_FILE" 2>&1
```

List all type errors with line numbers.

### 3.3 Profiling to find hotspots *(only if goals include `speed`)*

Before benchmarking all functions, use `cProfile` to pinpoint exactly where time is spent. This avoids benchmarking functions that aren't actually slow:

```bash
python3 -m cProfile -s cumulative "$TARGET_FILE" 2>&1 | head -30
```

If the file isn't directly runnable, profile via a short script:

```python
import cProfile, pstats, io
import importlib.util, sys

spec = importlib.util.spec_from_file_location("target", "<TARGET_FILE>")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

pr = cProfile.Profile()
pr.enable()
# Call the suspected slow function with realistic input here
mod.<function>(<args>)
pr.disable()

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(15)
print(s.getvalue())
```

From the profile, record which functions consume the most cumulative time. Use `--function` to focus the benchmark on those only. Look for:

| Signal | What to look for |
|:-------|:----------------|
| Slow loop | `for x in list` where list comprehension or `map()` would do |
| Repeated computation | Same value computed inside a loop — move outside |
| Unnecessary copies | List/dict reconstructed each call — use in-place ops |
| String concatenation in loop | Use `str.join()` or `io.StringIO` |
| Sorting without key | `sorted(items, key=lambda x: x.val)` vs `attrgetter` |
| N+1 pattern | Nested loops where one is a lookup — use a dict |
| Suboptimal data structure | `list.index()` called repeatedly — use `set` or `dict` |
| Pure Python where numpy/builtin helps | Numeric loops that could use `sum()`, `max()`, list comprehension |

### 3.4 Complexity analysis

```bash
python3 "$SKILL_DIR/scripts/complexity.py" --file "$TARGET_FILE" --per-function --json
```

Flag functions with cyclomatic > 10 or nesting > 4.

### 3.5 Questioner — structured profiling

Before building the attack plan, run the Questioner protocol to surface non-obvious
bottlenecks. Ask these structured questions and record answers:

1. **Where is time actually spent?** — Read cProfile output (3.3). Which functions
   dominate cumulative time? Are there surprise entries (e.g. `__hash__`, `copy.deepcopy`)?
2. **What data shapes drive performance?** — What are typical input sizes? Does the
   code handle edge cases differently (empty list, single element, very large)?
3. **What assumptions does the code make?** — Are there implicit invariants
   (sorted input, unique keys, non-null values) that could be exploited or are violated?
4. **What does the type checker say?** — ty errors often reveal type confusion that
   causes unnecessary coercions or defensive checks at runtime.
5. **What patterns repeat?** — Scan for copy-paste code, repeated computations,
   redundant validation across functions.

Record as `QUESTIONER_NOTES`. Use domain reasoning vocabulary:

| Signal | Keywords to use in attack plan |
|:-------|:------------------------------|
| Slow loop | hot path, tight loop, vectorize, amortize |
| Memory | peak allocation, object lifetime, allocation pressure |
| Type issues | coercion overhead, dynamic dispatch, monomorphic |
| Structure | invariant, precondition, early exit, short-circuit |
| Data structure | cache locality, hash collision, amortized cost |

### 3.6 Attack plan

Write a numbered list before touching any code:

```
Attack plan
───────────
1. [ruff E501] Lines too long — run ruff --fix for autofix, then adjust manually
   Why: 12 violations, auto-fixable
   Expected: ruff count drops by 12

2. [speed] parse_records() rebuilds output_list inside loop
   Why: O(n) append in a loop; pre-allocate or use list comprehension
   Expected: ~30–50% speedup based on profiling

3. [simplicity] validate_input() has cyclomatic=14, nesting=6
   Why: nested if-else chain — can be flattened with early returns
   Expected: complexity score drops ~40 points
```

Show the attack plan and confirm before proceeding.

---

## Phase Fix — Diagnose and repair broken Python  *(only when GOALS = fix)*

> Skip Phases 2.3–2.5 (benchmark / quality / complexity baselines), 3.3–3.5 (profiling, attack plan), and the Phase 5 loop. After Phase Fix, jump straight to Phase 6 (fix report).

The user has Python code that fails to import or run. The goal is a minimal, surgical fix that makes the code execute correctly without changing its intent. No optimization, no style cleanup — just the error, diagnosed and patched.

### Fix.1 — Capture the error

**Syntax / import errors** (caught before any code runs):
```bash
python3 -c "import ast; ast.parse(open('$TARGET_FILE').read()); print('syntax ok')"
python3 -c "import importlib.util; s=importlib.util.spec_from_file_location('m','$TARGET_FILE'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)" 2>&1
```

**Runtime errors** (only surface when code actually executes — caught by tests):
```bash
pytest "$TEST_FILE" -x --tb=short 2>&1 | head -50
```

**Type errors** (static — no execution needed):
```bash
ty check "$TARGET_FILE" 2>&1
```

Run all three. Record every error: class, message, file, line number.

Error triage — what each error class tells you:

| Error class | Caught by | Common cause |
|:------------|:----------|:-------------|
| `SyntaxError` | `ast.parse` | Typo, missing colon, mismatched parentheses, f-string issue |
| `IndentationError` | `ast.parse` | Mixed tabs/spaces, block dedented wrong |
| `ImportError` / `ModuleNotFoundError` | import | Missing dependency, wrong module name, circular import |
| `NameError` | runtime / pytest | Variable used before assignment, typo in name |
| `TypeError` | runtime / pytest | Wrong argument count, wrong type passed, `None` where value expected |
| `AttributeError` | runtime / pytest | Method called on wrong type, misspelled attribute, `None` propagated |
| `ValueError` | runtime / pytest | Unpacking wrong count, `int('abc')`, invalid enum value |
| `KeyError` | runtime / pytest | Dict key doesn't exist — missing `.get()` or wrong key name |
| `RecursionError` | runtime / pytest | Infinite recursion — base case missing |
| ty `error[possibly-unbound]` | ty | Variable assigned inside `if` but used outside — needs default or guard |
| ty `error[invalid-argument-type]` | ty | Function called with wrong type — fix call site or add `cast()` |

### Fix.2 — Identify root cause and apply minimal fix

Look at the exact error message and line number. Make the smallest change that fixes it:

| Symptom | Fix |
|:--------|:----|
| `SyntaxError: invalid syntax` near closing paren | Count opening vs closing parens on that line and above |
| `SyntaxError` in f-string | Avoid backslashes inside f-string expression — assign to variable first |
| `IndentationError` | Check if the file mixes tabs and spaces — `expand -t 4 $TARGET_FILE` to normalize |
| `ModuleNotFoundError: No module named 'X'` | Add `X` to dependencies (`uv add X`), or fix the import path |
| `ImportError: cannot import name 'X' from 'Y'` | Name was renamed or removed — check the module's actual exports |
| `NameError: name 'X' is not defined` | Typo, or used before assignment — fix spelling or move assignment earlier |
| `TypeError: X() missing N required positional arguments` | Caller is missing arguments — check the function signature |
| `TypeError: unsupported operand type(s) for +: 'int' and 'str'` | Type mismatch — add `str()` or `int()` conversion at the right point |
| `AttributeError: 'NoneType' object has no attribute 'X'` | A function returned `None` unexpectedly — add a None guard or fix the return |
| `AttributeError: 'X' object has no attribute 'Y'` | Typo in attribute name, or wrong object type passed |
| `KeyError: 'X'` | Use `dict.get('X')` or verify the key exists before access |
| `ValueError: too many values to unpack` | Unpacking tuple/list of wrong length — use `a, *rest = ...` or fix the source |
| `RecursionError` | Missing or unreachable base case in recursive function |

Make **one fix at a time** if there are multiple errors, starting with the one that blocks execution entirely (syntax errors first, then import errors, then runtime errors).

### Fix.3 — Verify

```bash
# Syntax clean?
python3 -c "import ast; ast.parse(open('$TARGET_FILE').read()); print('syntax ok')"

# Tests pass?
pytest "$TEST_FILE" -x --tb=short 2>&1
```

Both must pass. If a new error surfaces after the first fix, repeat Fix.2 → Fix.3 (up to 5 iterations). If a fix is not converging, stop and explain the remaining issue to the user clearly.

### Fix.4 — Commit

```bash
git add "$TARGET_FILE"
git commit -m "py-fix: <what was broken> — <what was changed>"
```

Then proceed to Phase 6 (fix report).

---

## Phase 4 — Rewrite

**One focused change per attempt.** Never batch multiple unrelated changes.

**For quality goals — always start with `ruff --fix`:**

```bash
ruff check "$TARGET_FILE" --fix
```

This auto-fixes import ordering, whitespace, `!= None` comparisons, deprecated typing aliases, and many style issues in a single pass. Run it as attempt #1 before any manual edits. Then re-check what's left:

```bash
python3 "$SKILL_DIR/scripts/check_quality.py" --file "$TARGET_FILE" --json
```

Only manually handle violations that `ruff --fix` couldn't resolve (bare `except`, mutable defaults, logic-dependent issues).

**What is allowed:**
- Replacing slow loops with list comprehensions, `map()`, `filter()`
- Using `dict`/`set` for O(1) lookups instead of `list.index()`
- Moving invariant computations outside loops
- Replacing string concatenation with `str.join()`
- Adding type annotations (fixes ty errors, doesn't break behavior)
- Running `ruff --fix` for auto-fixable violations (do this first)
- Flattening nested if-else with early returns / guard clauses
- Extracting repeated expressions to variables
- Replacing `lambda` with `operator.attrgetter`/`operator.itemgetter`
- Using `collections.Counter`, `itertools`, `functools.cache` where appropriate

**What is NOT allowed:**
- Changing function signatures in a way that breaks the test file
- Changing behavior — output must be identical for all inputs the tests cover
- Adding new dependencies not already in the project
- Touching test files

---

## Phase 5 — Validate, benchmark, and loop

### 5.1 Edit and commit

Edit `$TARGET_FILE` directly — the branch is isolated.

```bash
git add "$TARGET_FILE"
git commit -m "py-tune: attempt <N> — <one-line description>"
```

Commit before running tests so every attempt is in the git log.

### 5.2 Validate

```bash
pytest "$TEST_FILE" -v 2>&1
```

**If tests fail:** fix the regression immediately, or revert:
```bash
cp "$ORIGINAL_BACKUP" "$TARGET_FILE"   # restore original
git checkout HEAD "$TARGET_FILE"       # or revert to last kept commit
```
Do not move forward with a failing test suite.

### 5.3 Benchmark and quality check

```bash
python3 "$SKILL_DIR/scripts/benchmark.py" \
  --file "$TARGET_FILE" \
  --test-file "$TEST_FILE" \
  [--function "$TARGET_FUNCTION"] \
  --n-runs "$N_RUNS" \
  --json

python3 "$SKILL_DIR/scripts/check_quality.py" --file "$TARGET_FILE" --json

python3 "$SKILL_DIR/scripts/complexity.py" --file "$TARGET_FILE" --json
```

### 5.4 Inspector — validate beyond the metric

Before deciding keep/revert, run the Inspector checklist. A change that improves
the metric but fails inspection gets rejected.

**Inspector checklist:**

| Check | Pass condition |
|:------|:---------------|
| Metric improved | Value better than `BEST_*` (or held if simplification pass) |
| Change is focused | One idea per attempt — no bundled unrelated changes |
| No complexity explosion | LOC delta and cyclomatic delta proportional to gain |
| Code is reviewable | A human reviewer would accept this without "what does this do?" |
| No benchmark gaming | No hardcoded values that only work for the specific test input |
| No regressions | Test suite green, type checker not worse, no new ruff violations |
| Maintainability preserved | No `# noqa`, no suppressed warnings, no cryptic variable names |
| Description accurate | Commit message matches actual code change (no hallucinated improvements) |
| Improvement is real | Metric delta is genuine, not noise or measurement artifact |

**Inspector verdict:**
- `PASS` — all checks satisfied → proceed to DECIDE
- `FAIL` — record which check(s) failed → force discard with status `inspector-reject`
- `WARN` — borderline (e.g. +15 LOC for 40% speedup) → keep but flag in description

Record as `INSPECTOR_NOTES` in the attempt log description.

### 5.5 Decide: keep or revert

Use `BEST_*` values (start from baseline, updated on each kept improvement):

| Goal | Keep if |
|:-----|:--------|
| `speed` | `mean_ms < BEST_MEAN_MS` and improvement is statistically meaningful (new CI below old CI) |
| `quality` | `ruff_count + ty_count < BEST_QUALITY_COUNT` |
| `simplicity` | `complexity_score < BEST_COMPLEXITY_SCORE` |
| combined | ALL active goals must improve (or at least not regress) |

Inspector must also pass (see 5.4). A metric improvement with inspector failure = discard.

```
✅ IMPROVED + INSPECTOR PASS  → keep commit, update BEST_* values
❌ SAME/WORSE                 → git checkout HEAD "$TARGET_FILE"
⚠️ IMPROVED + INSPECTOR FAIL  → git checkout HEAD "$TARGET_FILE", log as "inspector-reject"
💥 TEST FAIL                   → fix or revert, re-run
```

### 5.6 Log the attempt

Maintain a TSV log `py-tune-results.tsv`:

```
N  sha  mean_ms  ruff  ty  complexity  status  description
```

### 5.7 Autonomous loop

Run continuously. Never pause to ask "should I continue?". The full iteration is:
Question → Think → Score → Reflect → Edit → Commit → Validate → Benchmark → Inspect → Decide → Log → repeat.

**SCORE** — Before each edit, rate the hypothesis (1–10 each):
- **Impact**: how much metric improvement expected?
- **Feasibility**: how likely to work without breaking tests?
- **Novelty**: how different from prior attempts? (check `py-tune-results.tsv`)

Average ≥ 5 → proceed. Below 5 → generate better hypothesis. Skip on attempt #1.

**REFLECT** — Self-check before editing:
- What assumption could be wrong?
- Has something similar already failed? (scan TSV)
- Am I stuck in a local optimum? (3+ keeps in same area → switch axis)
- Could this change break something I won't measure?

If reflection reveals a flaw → revise hypothesis and re-SCORE.

Stop only when:
- No further improvements found after 2 consecutive failed attempts per remaining goal
- All goals are satisfied (no violations, no errors, complexity below a reasonable threshold)
- User interrupts

Strategy priority by goal:

**Speed:**
1. Fix N+1 / repeated lookup patterns first (highest leverage)
2. Move loop-invariant computations outside loops
3. Replace Python loops with built-ins / comprehensions
4. Use more efficient data structures

**Quality:**
1. `ruff check --fix` first (attempt #1) — gets rid of all auto-fixable violations in one shot
2. Fix remaining ruff violations manually, highest severity first (B > E > W > C)
3. Add type annotations for ty errors — start with function signatures, then return types, then variables
4. Fix ty errors that require logic changes (e.g. `dict.get` passed to `max` — use a lambda instead)

**Simplicity:**
1. Flatten deepest nesting first (early returns, guard clauses)
2. Extract repeated expressions
3. Break up high-cyclomatic functions into smaller ones
4. Remove dead code

---

## Phase 6 — Report

**If GOALS = fix**, present the fix report:

```
## Python Fix Report

### Error diagnosed
<exact error class, message, file, and line number>

### Root cause
<one sentence: what was wrong and why>

### Fix applied
<show the specific lines changed — before/after>

### Verification
pytest: ✅ N tests passed
Syntax check: ✅ clean

### Fixed code
<the corrected section of the file>
```

**Otherwise** (speed / quality / simplicity), present the tuning summary.

```bash
cat py-tune-results.tsv
git log --oneline <baseline-sha>..HEAD
```

Present:

```
## Python Autotuner Report

### Run summary
- Attempts: N total / K kept / M discarded
- File: <TARGET_FILE>
- Branch: <BRANCH>

### Metrics: baseline → final
| Metric         | Baseline | Final    | Delta  |
|:---------------|:---------|:---------|:-------|
| Speed (ms)     | x.xx     | x.xx     | -xx%   |
| Ruff violations| N        | N        | -N     |
| ty errors      | N        | N        | -N     |
| Complexity     | N        | N        | -N     |
| LOC            | N        | N        | -N     |

### Attempt log
| # | Mean(ms) | Ruff | ty | Complexity | Status  | Description |
|:--|:---------|:-----|:---|:-----------|:--------|:------------|

### Analysis (original)
<bottlenecks identified in Phase 3>

### Optimizations applied (kept only)
1. <what changed — why — effect>

### Final code diff
<git diff <baseline-sha>..HEAD -- $TARGET_FILE>

### Conclusion
<one paragraph: what changed, why it helped, any caveats>

### Remaining issues (not fixed)
<anything identified but outside scope or too risky to change>

### Run-level review
Rate the entire optimization run:
| Axis           | Score (1–10) | Notes |
|:---------------|:------------|:------|
| Soundness      |             | Are improvements real or measurement artifacts? |
| Quality        |             | Would a senior engineer approve the final diff? |
| Significance   |             | Is the improvement worth the complexity added? |
| Completeness   |             | Were the most promising directions explored? |

Flags:
- Fragile improvements (metric up but change may not generalize)
- Unexplored promising directions
- Inspector-rejected experiments worth revisiting
- Any sign of overfitting to benchmark input
```

---

## Troubleshooting

| Error | Fix |
|:------|:----|
| `Tests fail at baseline` | Fix the code first — autotuner requires a green test suite to start |
| `No test file found` | Pass `--test-file path/to/test_file.py` explicitly |
| `ruff: command not found` | `uv tool install ruff` |
| `ty: command not found` | `uv tool install ty` |
| `benchmark_spec.py not found` | Create it next to the target file — see Phase 2.3 for the template |
| `BENCHMARKS dict is empty` | Check benchmark_spec.py — must define at least one `name: lambda: fn(args)` entry |
| `radon: command not found` | `uv tool install radon` — or use bundled `scripts/complexity.py` as fallback |
| `--explain-only` made no edits | Correct — explain-only stops after Phase 3. Run without the flag to apply changes. |
| Code has errors at baseline | Use `--goals fix` — the fix phase diagnoses and repairs without benchmarking |
| `SyntaxError` before tests even run | Fix phase catches this at `ast.parse` before pytest is invoked |
| `Revert fails` | Use `cp "$ORIGINAL_BACKUP" "$TARGET_FILE"` to restore from the pre-run copy |
| `Stat sig unclear` | With N_RUNS < 5, CI overlap is common — increase `--n-runs` |
