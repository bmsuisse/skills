---
title: Autoresearch Loop
description: Autonomous iterative experimentation loop for Python, SQL, ML, and Spark projects.
---

# Autoresearch Loop

**Skill:** `autoresearch` · **Plugin:** `coding@bmsuisse-skills`

An autonomous experiment loop: hypothesis → implement → measure → keep or revert → repeat.

## When to use

- Optimizing a metric iteratively (query speed, model accuracy, memory usage)
- Systematically reducing type errors or test failures
- Benchmarking alternative implementations
- Any task where the goal is quantifiable and experiments are cheap to run

## Invoke

```
/autoresearch
```

Then describe your goal:

```
Reduce the p95 query latency of the user feed endpoint from 800ms to under 200ms.
Constraint: test suite must stay green. Budget: 10 experiments.
```

## The loop

```
1. Measure baseline         → record metric
2. Hypothesize improvement  → pick smallest change likely to help
3. Implement               → surgical edit only
4. Measure                 → compare to baseline
5. Keep or revert          → revert if metric didn't improve
6. Commit if kept          → one commit per kept experiment
7. Repeat
```

## Metric examples

| Goal | Metric command |
|---|---|
| Execution speed | `hyperfine --warmup 1 'uv run python script.py'` |
| Test pass rate | `uv run pytest --tb=no -q 2>&1 \| grep "passed"` |
| Type errors | `uv run ty check 2>/dev/null \| grep -c "^error["` |
| SQL query time | `EXPLAIN ANALYZE <query>` → parse `Execution Time` |

## Constraints

Set hard constraints upfront — the loop respects them as invariants:

- `uv run pytest` must stay green
- `uv run ty check` must stay at zero errors
- Run time must not exceed 2× baseline

## Spark/Databricks

The loop works with Spark Connect — each experiment submits a job to the cluster and reads metrics from stdout or MLflow. Account for cold start time (~1–2 min) in your baseline.

```
Spark-specific: use hyperfine --warmup 1 (not 3+) to avoid unnecessary cluster compute cost.
```
