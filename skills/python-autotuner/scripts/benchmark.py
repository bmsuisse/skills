#!/usr/bin/env python3
"""Benchmark Python functions using timeit — no pytest-benchmark fixtures needed.

Works on any Python file. Requires a benchmark_spec.py file next to the target.
pytest handles correctness; this script handles performance. Clean separation.

benchmark_spec.py format
────────────────────────
Create this file next to the target module. Import from the target and define
BENCHMARKS as a dict mapping benchmark names to zero-arg callables:

    from processor import sum_squares, find_duplicates

    _DATA = list(range(10_000))
    _DUPS = [i % 100 for i in range(1_000)]

    BENCHMARKS = {
        "sum_squares": lambda: sum_squares(_DATA),
        "find_duplicates": lambda: find_duplicates(_DUPS),
    }

Usage
─────
    # Run all benchmarks defined in benchmark_spec.py next to processor.py
    python3 scripts/benchmark.py --file mymodule/processor.py --n-runs 10 --json

    # Filter to one benchmark
    python3 scripts/benchmark.py --file processor.py --function find_duplicates --json

    # Compare against a saved baseline
    python3 scripts/benchmark.py --file processor.py --compare baseline.json --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path


# ── stats ──────────────────────────────────────────────────────────────────────

def _stats(times_s: list[float]) -> dict:
    """Compute timing stats from a list of per-call wall-clock seconds."""
    n = len(times_s)
    mean = statistics.mean(times_s)
    std = statistics.stdev(times_s) if n > 1 else 0.0
    ci_margin = 2.0 * std  # ~95% CI (approximate; exact needs t-dist for small n)
    return {
        "mean_ms": round(mean * 1000, 4),
        "std_ms": round(std * 1000, 4),
        "min_ms": round(min(times_s) * 1000, 4),
        "max_ms": round(max(times_s) * 1000, 4),
        "ci_low_ms": round(max(0.0, mean - ci_margin) * 1000, 4),
        "ci_high_ms": round((mean + ci_margin) * 1000, 4),
        "rounds": n,
    }


def _ci_no_overlap(a: dict, b: dict) -> bool:
    """True if b's CI is entirely below a's — b is statistically faster."""
    return b["ci_high_ms"] < a["ci_low_ms"]


# ── module loading ─────────────────────────────────────────────────────────────

def _load_module_from_path(path: Path):
    """Import a .py file as a module by path, without installing it."""
    parent = str(path.parent.resolve())
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_spec(target_file: str) -> dict:
    """
    Load BENCHMARKS from benchmark_spec.py next to the target file.
    Returns dict of {name: zero-arg callable}.
    Exits with a helpful message if spec not found.
    """
    target = Path(target_file).resolve()
    spec_path = target.parent / "benchmark_spec.py"

    if not spec_path.exists():
        print(
            f"benchmark_spec.py not found at {spec_path}\n\n"
            "Create it with a BENCHMARKS dict. Example:\n\n"
            f"    from {target.stem} import <your_function>\n\n"
            "    _SAMPLE = <realistic input data>\n\n"
            "    BENCHMARKS = {\n"
            f'        "<function_name>": lambda: <your_function>(_SAMPLE),\n'
            "    }\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Add target's directory to sys.path so the spec can import from it
    parent = str(target.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    mod = _load_module_from_path(spec_path)
    benchmarks = getattr(mod, "BENCHMARKS", None)

    if not isinstance(benchmarks, dict) or not benchmarks:
        print(
            f"benchmark_spec.py at {spec_path} must define a non-empty BENCHMARKS dict.",
            file=sys.stderr,
        )
        sys.exit(1)

    return benchmarks


# ── timing ─────────────────────────────────────────────────────────────────────

def _time_callable(fn, n_warmup: int, n_runs: int) -> list[float]:
    """Time a zero-arg callable. Returns per-call wall-clock seconds."""
    import timeit

    for _ in range(n_warmup):
        fn()

    return [timeit.timeit(fn, number=1) for _ in range(n_runs)]


# ── comparison ─────────────────────────────────────────────────────────────────

def _compare(baseline: dict, optimized: dict) -> list[dict]:
    """Compute speedup for each benchmark present in both runs."""
    b_map = {b["name"]: b for b in baseline.get("benchmarks", [])}
    o_map = {b["name"]: b for b in optimized.get("benchmarks", [])}

    comparisons = []
    for name, orig in b_map.items():
        if name not in o_map:
            continue
        opt = o_map[name]
        speedup = orig["mean_ms"] / opt["mean_ms"] if opt["mean_ms"] > 0 else 1.0
        sig = _ci_no_overlap(orig, opt)
        comparisons.append({
            "name": name,
            "original_mean_ms": orig["mean_ms"],
            "optimized_mean_ms": opt["mean_ms"],
            "speedup": round(speedup, 3),
            "statistically_significant": sig,
            "improved": speedup > 1.0 and sig,
        })
    return sorted(comparisons, key=lambda c: -c["speedup"])


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Python functions with timeit. No pytest fixtures needed."
    )
    parser.add_argument("--file", required=True, help="Target .py file being tuned")
    parser.add_argument("--function", help="Filter: only run benchmarks whose name contains this")
    parser.add_argument("--n-runs", type=int, default=10, help="Timed iterations per benchmark (default 10)")
    parser.add_argument("--n-warmup", type=int, default=3, help="Warmup iterations before timing (default 3)")
    parser.add_argument("--compare", help="Path to a saved baseline benchmark JSON for before/after comparison")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    benchmarks = _load_spec(args.file)

    if args.function:
        benchmarks = {k: v for k, v in benchmarks.items() if args.function.lower() in k.lower()}
        if not benchmarks:
            print(f"No benchmarks matching --function {args.function!r}", file=sys.stderr)
            sys.exit(1)

    results = []
    for name, fn in benchmarks.items():
        times = _time_callable(fn, n_warmup=args.n_warmup, n_runs=args.n_runs)
        entry = {"name": name, **_stats(times)}
        results.append(entry)
        if not args.as_json:
            print(
                f"  {name}: {entry['mean_ms']:.3f}ms ± {entry['std_ms']:.3f}ms"
                f"  95%CI [{entry['ci_low_ms']:.3f}, {entry['ci_high_ms']:.3f}]"
                f"  ({entry['rounds']} runs)"
            )

    output: dict = {"benchmarks": results}

    if args.compare:
        with open(args.compare) as f:
            baseline = json.load(f)
        output["comparison"] = _compare(baseline, output)
        if not args.as_json:
            print("\nComparison vs baseline:")
            for c in output["comparison"]:
                label = "✅ stat.sig." if c["statistically_significant"] else "⚠️  within noise"
                print(
                    f"  {c['name']}: {c['speedup']:.2f}x  "
                    f"({c['original_mean_ms']:.3f}ms → {c['optimized_mean_ms']:.3f}ms)  {label}"
                )

    if args.as_json:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
