---
name: autoresearch
plugin: coding
description: >
  Autonomous iterative experimentation loop for Python, SQL, and ML projects.
  Guides you through defining a measurable goal, then runs an autonomous loop of
  code changes, measurements, and keep/revert decisions until you stop it.
  Use this skill whenever you want to: optimize Python runtime (cProfile, scalene,
  hyperfine), reduce SQL query time (EXPLAIN ANALYZE, pg_stat_statements), improve
  pytest pass rate or coverage, fix pyright errors systematically, tune ML training
  metrics (loss, accuracy, F1), reduce memory usage (tracemalloc, memory_profiler),
  or run any iterative hill-climbing experiment where each attempt is measurable.
  Trigger on: "optimize this", "autoopt", "autoresearch", "keep trying until it's
  faster", "improve test coverage automatically", "hill-climb this", "run experiments",
  "iterate autonomously", "keep going until it passes", "optimize SQL performance",
  "tune this model", "reduce pyright errors automatically".
  DO NOT USE FOR: one-shot fixes, code review without a metric, tasks with no
  measurable outcome, or when you just want a single suggestion.
compatibility: Requires git (project must be a git repository) and terminal access.
---

# Autoresearch — Autonomous Iterative Optimization

You define the goal and how to measure it. The agent does the rest: hypothesize, edit,
measure, keep or revert — running autonomously until you stop it or the budget runs out.

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch),
adapted for Python, SQL, pytest, pyright, and ML workflows.

> [!IMPORTANT]
> Every experiment is committed before running, and reverted on failure.
> The branch only ever advances on real improvements.

---

## Phase 1 — Setup (interactive)

Work through these questions with the user before touching any code.
Do not skip or assume answers.

### 1.1 Goal

Ask:

> **What are you trying to improve?**
>
> Examples: execution time, memory usage, pytest pass rate, pyright error count,
> SQL query latency, model accuracy, training throughput, bundle size.

### 1.2 Metric command

Ask:

> **What command produces the metric, and how do I read the number from its output?**
>
> 1. **Command** — the exact shell command to run
> 2. **Extraction** — regex, line number, JSON path, or description of what to parse
> 3. **Direction** — lower is better, or higher is better?

Refer to the [domain quick-reference](#domain-metric-quick-reference) below for
ready-made commands if the user is unsure.

Record:
- `METRIC_COMMAND`
- `METRIC_EXTRACTION`
- `METRIC_DIRECTION` (`lower_is_better` | `higher_is_better`)

### 1.3 Scope

Ask:

> **Which files or directories may I edit?**
> **Which are off-limits?**

Record:
- `IN_SCOPE` — files/dirs the agent may modify
- `OUT_OF_SCOPE` — must not be touched

### 1.4 Constraints

Ask:

> **Any constraints I should respect?**
>
> Examples: no new dependencies, must keep existing tests green, public API must
> stay stable, max 2 min per run, must stay type-clean (pyright 0 errors), VRAM
> budget, complexity budget.

Record as `CONSTRAINTS`.

### 1.4b Web search

Ask:

> **May I search the web for optimization ideas, documentation, or techniques?**
>
> Web search lets me look up library docs, algorithm papers, Stack Overflow
> answers, and benchmarking guides to generate better hypotheses — especially
> useful for ML tuning, SQL optimization, and unfamiliar libraries.
>
> Options: `yes` (search freely), `ask` (propose each query before running),
> `no` (stay offline, codebase only).

Record as `WEB_SEARCH` (`yes` | `ask` | `no`, default `no`).

### 1.5 Budget

Ask:

> **How many experiments, or keep going until interrupted?**

Record as `MAX_EXPERIMENTS` (number or `unlimited`).

### 1.6 Simplicity policy

State the default and ask for adjustments:

> **Default:** simpler beats marginally faster. Removing code while holding or
> improving the metric is a win. Complexity has a cost — weigh it honestly against
> the gain. OK to proceed with this policy, or do you want to adjust it?

Record any adjustment as `SIMPLICITY_POLICY`.

### 1.7 Confirm

Present a summary table and wait for explicit confirmation before continuing.

| Parameter         | Value |
| ----------------- | ----- |
| Goal              |       |
| Metric command    |       |
| Metric extraction |       |
| Direction         |       |
| In-scope          |       |
| Out-of-scope      |       |
| Constraints       |       |
| Max experiments   |       |
| Simplicity policy |       |
| Web search        |       |

---

## Parallel autoresearch

Run multiple experiment loops simultaneously, each on its own branch and working
directory, using `git worktree`. Useful when you want to race two hypotheses, explore
independent scopes concurrently, or keep your main editor on `main` while experiments run.

### When to use parallel mode

- Two or more independent scopes (different files or modules) that won't conflict
- Long-running metric commands where waiting for one loop blocks progress
- Competing strategies you want to benchmark side-by-side

### Setup

For each parallel run, create a dedicated worktree **before** starting its loop:

```bash
# In the repo root — repeat for each parallel run
RUN_ID_A="<goal-a>"   # e.g. etl-runtime
RUN_ID_B="<goal-b>"   # e.g. pyright-errors

git worktree add ../<repo>-${RUN_ID_A} -b autoresearch/${RUN_ID_A}
git worktree add ../<repo>-${RUN_ID_B} -b autoresearch/${RUN_ID_B}
```

Each worktree is a sibling directory with its own `HEAD` and index — commits,
resets, and file edits in one worktree are completely invisible to the others.

### Guidelines

| Rule | Reason |
| ---- | ------ |
| **Non-overlapping `IN_SCOPE`** | Two loops editing the same file will overwrite each other's changes — the merge conflict is yours to resolve |
| **Each run gets its own worktree** | Never share a directory between two loops |
| **Separate `RESULTS_FILE` per run** | Use the unique `RUN_ID` — they naturally don't collide |
| **Merge order matters** | When both runs finish, merge the one with the larger improvement first; re-run the other's baseline before merging it to get an honest combined measurement |
| **VS Code workspace** | `File → Add Folder to Workspace` for each worktree directory — all runs visible side-by-side |

### Cleanup

When a parallel run finishes, remove its worktree:

```bash
git worktree remove ../<repo>-${RUN_ID_A}   # removes directory + unregisters
# or, if the run produced no improvement:
git worktree remove --force ../<repo>-${RUN_ID_A}
git branch -D autoresearch/${RUN_ID_A}
```

List active worktrees at any time:

```bash
git worktree list
```

---

## Phase 2 — Branch & baseline

1. **Generate a run ID** — a short goal slug, e.g. `pytest-passrate`.
   This ID is used for all artifacts of this run so multiple runs never collide.

   ```bash
   RUN_ID="<goal-slug>"   # e.g. pytest-passrate
   RESULTS_FILE="autoresearch-${RUN_ID}.tsv"
   LOG_FILE="autoresearch-${RUN_ID}.log"
   ```

2. **Create a branch** — propose `autoresearch/<run-id>`, create it:

   ```bash
   git checkout -b autoresearch/${RUN_ID}
   ```

3. **Read in-scope files** — build full context before making any changes.

4. **Initialize `$RESULTS_FILE`** in the repo root:

   ```
   experiment	commit	metric	status	description
   ```

   Register both files in `.git/info/exclude` (append only — never modify tracked files):

   ```bash
   echo "${RESULTS_FILE}" >> .git/info/exclude
   echo "${LOG_FILE}"     >> .git/info/exclude
   ```

5. **Run the baseline** — execute `METRIC_COMMAND`, extract the value, record as
   experiment `0` with status `baseline`.

6. **Report** to the user:

   > Baseline: **\[metric\] = \[value\]**. Run ID: `<run-id>`. Starting experiment loop.

---

## Phase 3 — Experiment loop

Run continuously. Never pause to ask "should I continue?". Stop only when:
- `MAX_EXPERIMENTS` is reached, or
- the user interrupts

### Each iteration

```
THINK   Analyze prior results + current code.
        Form a specific hypothesis: "X should improve Y because Z."
        If WEB_SEARCH is `yes` or `ask` and you are stuck or entering a new
        domain (e.g. unfamiliar library, ML algorithm, SQL planner behavior),
        search the web for relevant techniques, docs, or benchmarks before
        forming the hypothesis. For `ask`, state the proposed query and wait
        for confirmation. Log the source URL in the description column of the
        TSV when a web result directly inspired the experiment.
        Follow experiment strategy priority below.

EDIT    Make one focused change to in-scope files.
        Keep it minimal — one idea per experiment.

COMMIT  Stage only in-scope files, then commit:
        git add <IN_SCOPE files> && git commit
        Message format: "experiment: <short description>"

RUN     Execute METRIC_COMMAND, redirect all output:
        <command> > $LOG_FILE 2>&1

MEASURE Extract the metric from $LOG_FILE.
        On failure: read the last 50 lines of run.log for the error.

DECIDE  Compare to current best:
        ✅ IMPROVED  → keep commit, update best, log status = "keep"
        ❌ SAME/WORSE → revert only in-scope files:
                       git reset HEAD~1               # soft-reset: undo commit, keep working tree
                       git restore <IN_SCOPE files>   # discard changes to in-scope files only
                       log status = "discard"
        💥 CRASH     → attempt up to 2 quick fixes (typo, import, simple error),
                       amend commit, re-run. If still broken, soft-reset and
                       restore only in-scope files; log status = "crash".

LOG     Append to results.tsv:
        <N>	<commit>	<value>	<status>	<description>
```

### Experiment strategy

Follow this priority order:

1. **Low-hanging fruit** — obvious inefficiencies, trivial parameter changes
2. **Follow promising directions** — if something worked, probe further
3. **Diversify after plateaus** — 3–5 consecutive failures → switch strategy
4. **Combine winners** — if A and B each improved independently, try A+B
5. **Simplification passes** — periodically try removing code; hold the metric
6. **Bigger changes** — algorithmic or architectural changes after incremental ideas run dry

### Constraint enforcement

- **Time budget**: if a run exceeds 2× baseline duration, kill and treat as crash
- **Test integrity**: if constraints require green tests, run them after each experiment;
  revert if they break, even if the primary metric improved
- **Pyright/type safety**: if type-cleanliness is a constraint, run `pyright` after each
  change and revert if new errors appear

---

## Phase 4 — Report, cleanup & next steps

When the loop ends (budget reached or interrupted), work through all four sub-phases.

### 4.1 Results report

1. Print `$RESULTS_FILE` as a formatted table.
2. Summarize:
   - Total experiments / kept / discarded / crashed
   - Baseline → final metric, improvement %
   - Top 3 most impactful changes (by metric delta)
3. Show the git log of kept experiments:

   ```bash
   git log --oneline <start-commit>..HEAD
   ```

### 4.2 Cleanup

Remove run artifacts that are no longer needed. Ask the user once before deleting:

> Run complete. Clean up `$RESULTS_FILE` and `$LOG_FILE` from the working directory?
> (They stay in git history if you need them later.)

If confirmed:

```bash
rm -f "${RESULTS_FILE}" "${LOG_FILE}"
```

Also remove the excludes entries added in Phase 2 so the file is left tidy:

```bash
# removes the two lines added during setup (grep -v is safe here — no tracked files touched)
grep -v "^${RESULTS_FILE}$\|^${LOG_FILE}$" .git/info/exclude > /tmp/_exclude_tmp \
  && mv /tmp/_exclude_tmp .git/info/exclude
```

### 4.3 Proposed next steps

Present these as a checklist. Mark which apply based on what the run actually changed.

**Code quality**
- [ ] Run `/deslop` on changed files — automated optimization often leaves mechanical
      patterns, naming inconsistencies, or removed comments that need a pass
- [ ] Run `pyright` across the full project to confirm no new type errors leaked in
- [ ] Run the full test suite one final time on the current branch tip

**Commit hygiene**
- [ ] Squash experiment commits into one or a few logical commits before merging:
      ```bash
      git rebase -i <start-commit>
      ```
      Replace all `experiment:` commits with meaningful messages describing *what changed
      and why it helped*.
- [ ] Update any affected docstrings or inline comments that describe the old behavior

**Integration**
- [ ] Open a PR from `autoresearch/<run-id>` into your base branch
- [ ] Add a note in the PR description linking to the `$RESULTS_FILE` (or paste the
      summary table) so reviewers understand the methodology

**Further experimentation**
- [ ] Things not tried (ideas the loop skipped as too risky or complex):
      — algorithmic rewrites that would change public interfaces
      — dependency upgrades
      — schema or data-structure changes
      — parallelism / concurrency changes
      Decide which are worth pursuing manually.

### 4.4 Branch lifecycle

If the run produced no net improvement, offer to delete the branch cleanly:

```bash
git checkout <base-branch>
git branch -D autoresearch/${RUN_ID}
```

If improvements were made, leave the branch for PR review.

---

## Domain metric quick-reference

Use these when the user isn't sure how to phrase their metric command.

### Python runtime

```bash
# hyperfine (install: brew install hyperfine / pip install hyperfine)
hyperfine --warmup 3 'python my_script.py'
# → parse: "mean" field (lower is better)

# built-in timing
python -m timeit -n 100 -r 5 "import my_module; my_module.run()"

# cProfile summary
python -m cProfile -s cumtime my_script.py 2>&1 | head -20
```

### Python memory

```bash
# tracemalloc (add to script, or use wrapper)
python -c "
import tracemalloc, my_module
tracemalloc.start()
my_module.run()
current, peak = tracemalloc.get_traced_memory()
print(f'peak_kb={peak/1024:.1f}')
"
# → parse: peak_kb= line (lower is better)

# memory_profiler (pip install memory_profiler)
python -m memory_profiler my_script.py
```

### pytest

```bash
# pass rate
pytest --tb=no -q 2>&1 | tail -1
# → parse: "X passed" (higher is better)

# coverage
pytest --cov=src --cov-report=term-missing --tb=no -q 2>&1 | grep "TOTAL"
# → parse: last percentage (higher is better)

# duration
pytest --tb=no -q 2>&1 | grep "passed"
# → parse duration from summary line (lower is better)
```

### pyright

```bash
pyright --outputjson 2>/dev/null | python -c "
import json,sys; d=json.load(sys.stdin)
print('errors=' + str(d['summary']['errorCount']))
"
# → parse: errors= (lower is better)

# simpler: just count error lines
pyright 2>&1 | grep -c "error:"
```

### SQL (PostgreSQL)

```bash
# query duration via psql (wrap your query in EXPLAIN ANALYZE)
psql $DATABASE_URL -c "EXPLAIN (ANALYZE, FORMAT JSON) <your query>" \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d[0]['Execution Time'])"
# → parse: Execution Time (lower is better)

# if using pgbench
pgbench -c 5 -T 30 $DATABASE_URL 2>&1 | grep "tps ="
# → parse: tps value (higher is better)
```

### Machine learning

```bash
# training run — capture final metric from stdout
python train.py --epochs 10 2>&1 | grep "val_loss" | tail -1
# → parse: val_loss= value (lower is better)

# sklearn cross-validation
python -c "
from sklearn.model_selection import cross_val_score
import numpy as np, my_model, my_data
X, y = my_data.load()
scores = cross_val_score(my_model.build(), X, y, cv=5, scoring='f1_macro')
print(f'f1={np.mean(scores):.4f}')
"
# → parse: f1= (higher is better)
```

---

## Results TSV format

Filename: `autoresearch-<run-id>.tsv` (e.g. `autoresearch-pytest-passrate.tsv`)

Tab-separated, 5 columns:

```
experiment	commit	metric	status	description
0	a1b2c3d	142.3	baseline	unmodified code
1	b2c3d4e	138.1	keep	replace list comprehension with generator
2	c3d4e5f	145.0	discard	switch to numpy vectorization (slower on small data)
3	d4e5f6g	0.0	crash	add numba jit (import error, unfixable)
4	e5f6g7h	131.4	keep	cache repeated db lookups with lru_cache
```

---

## Key principles

| Principle         | Why it matters                                                              |
| ----------------- | --------------------------------------------------------------------------- |
| Measure everything | An unmeasured change is a guess. Every experiment has a number.            |
| Revert failures    | The branch tells the true story — only improvements survive.               |
| Stay autonomous    | Stopping to ask breaks the loop. Think harder instead.                     |
| Simplicity costs   | Every line added is future maintenance. Weigh it honestly.                 |
| Log everything     | The TSV is the research journal. Future you will thank present you.        |
