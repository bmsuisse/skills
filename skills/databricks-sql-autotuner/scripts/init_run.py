#!/usr/bin/env python3
"""Initialize a SQL autotuner session: create branch, set up files, run baseline.

Must be run with the autotuner venv Python:
    .venv_autotuner/bin/python scripts/init_run.py [options]

What it does:
    1. Creates git branch sql-tune/<run-id>
    2. Sets up ORIGINAL_FILE and QUERY_FILE (copies original → optimized if --optimized given)
    3. Excludes the TSV/log from git and writes the TSV header
    4. Runs the baseline benchmark (original vs original) via tune.py
    5. Prints a JSON summary with env vars ready for Claude to use in Phase 5b

Usage:
    .venv_autotuner/bin/python scripts/init_run.py \\
        --profile my-profile --cluster-id 0123-456789-abc \\
        --original @queries/slow_report.sql \\
        [--optimized optimized.sql] \\
        [--run-id sales-summary] \\
        [--n-runs 3] \\
        [--catalog my_catalog] [--schema my_schema] \\
        [--timing-count] [--global-temp]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TUNE_PY = Path(__file__).parent / "tune.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def derive_run_id(original_arg: str) -> str:
    if original_arg.startswith("@"):
        stem = Path(original_arg[1:]).stem
        slug = slugify(stem)
        return slug if slug else f"run-{int(time.time())}"
    return f"run-{int(time.time())}"


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check)


def in_git_repo() -> bool:
    return git("rev-parse", "--git-dir", check=False).returncode == 0


def current_sha() -> str:
    r = git("rev-parse", "--short", "HEAD", check=False)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def run_tune(extra_args: list[str]) -> dict:
    """Run tune.py with the given args and return the parsed JSON result."""
    cmd = [sys.executable, str(TUNE_PY)] + extra_args
    print(f"[baseline] {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        print(f"[error] tune.py exited {result.returncode}", file=sys.stderr)
        sys.exit(1)
    # tune.py prints JSON to stdout
    stdout = result.stdout.strip()
    # Strip leading '=' separator line if present
    lines = [l for l in stdout.splitlines() if not l.startswith("=")]
    try:
        return json.loads("\n".join(lines))
    except json.JSONDecodeError:
        print(f"[error] Could not parse tune.py output:\n{stdout}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialise a SQL autotuner session (branch + baseline).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--cluster-id", required=True, dest="cluster_id")
    parser.add_argument("--original", required=True, help="SQL string or @path/to/file.sql")
    parser.add_argument("--optimized", help="Path for the optimized query file (separate output)")
    parser.add_argument("--run-id", dest="run_id", help="Branch slug (auto-derived from filename if omitted)")
    parser.add_argument("--n-runs", type=int, default=3, dest="n_runs")
    parser.add_argument("--catalog")
    parser.add_argument("--schema")
    parser.add_argument("--timing-count", action="store_true", dest="timing_count")
    parser.add_argument("--global-temp", action="store_true", dest="global_temp")
    args = parser.parse_args()

    if args.n_runs < 1:
        print("[error] --n-runs must be at least 1", file=sys.stderr)
        sys.exit(1)
    if args.n_runs == 1:
        print("[warn] --n-runs 1: single run — for meaningful statistics use 2 or more", file=sys.stderr)

    run_id = args.run_id or derive_run_id(args.original)
    results_file = f"sqltune-{run_id}.tsv"
    log_file = f"sqltune-{run_id}.log"

    # --- Git branch ---
    branch_name: str | None = None
    if in_git_repo():
        branch_name = f"sql-tune/{run_id}"
        r = git("checkout", "-b", branch_name, check=False)
        if r.returncode == 0:
            print(f"[git] Created branch: {branch_name}", file=sys.stderr)
        else:
            print(f"[git] Branch already exists or failed: {r.stderr.strip()}", file=sys.stderr)
            branch_name = None
    else:
        print("[warn] Not in a git repository — skipping branch creation.", file=sys.stderr)

    # --- Working files ---
    if args.original.startswith("@"):
        original_file = Path(args.original[1:])
        if not original_file.exists():
            print(f"[error] Query file not found: {original_file}", file=sys.stderr)
            sys.exit(1)
    else:
        original_file = Path("query.sql")
        original_file.write_text(args.original, encoding="utf-8")
        git("add", str(original_file), check=False)
        print(f"[files] Wrote inline SQL to {original_file}", file=sys.stderr)

    if args.optimized:
        query_file = Path(args.optimized)
        shutil.copy(original_file, query_file)
        git("add", str(query_file), check=False)
        print(f"[files] Copied original → {query_file}", file=sys.stderr)
    else:
        query_file = original_file

    # --- Exclude TSV/log from git tracking ---
    if in_git_repo():
        exclude_path = Path(".git/info/exclude")
        existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
        to_add = "".join(
            f"{name}\n"
            for name in (results_file, log_file)
            if name not in existing
        )
        if to_add:
            with exclude_path.open("a", encoding="utf-8") as f:
                f.write(to_add)

    # --- TSV header ---
    Path(results_file).write_text(
        "attempt\tcommit\tmean_s\tspeedup\tstatus\tdescription\n",
        encoding="utf-8",
    )
    print(f"[tsv] Initialized {results_file}", file=sys.stderr)

    # --- Baseline benchmark ---
    print(f"\n[baseline] Running baseline ({args.n_runs} runs, original vs original)...", file=sys.stderr)
    tune_args = [
        "--profile", args.profile,
        "--cluster-id", args.cluster_id,
        "--original", f"@{original_file}",
        "--optimized", f"@{original_file}",
        "--n-runs", str(args.n_runs),
    ]
    if args.catalog:
        tune_args += ["--catalog", args.catalog]
    if args.schema:
        tune_args += ["--schema", args.schema]
    if args.timing_count:
        tune_args.append("--timing-count")
    if args.global_temp:
        tune_args.append("--global-temp")

    result = run_tune(tune_args)
    baseline_mean = result["original"]["mean_s"]
    sha = current_sha()

    # Append baseline row to TSV
    with Path(results_file).open("a", encoding="utf-8") as f:
        f.write(f"0\t{sha}\t{baseline_mean}\t1.0\tbaseline\toriginal query\n")

    # --- Summary ---
    w = 56
    print("\n" + "=" * w, file=sys.stderr)
    print("  Session ready", file=sys.stderr)
    print("=" * w, file=sys.stderr)
    print(f"  Run ID        : {run_id}", file=sys.stderr)
    print(f"  Baseline mean : {baseline_mean}s", file=sys.stderr)
    print(f"  Branch        : {branch_name or '(none)'}", file=sys.stderr)
    print(f"  ORIGINAL_FILE : {original_file}", file=sys.stderr)
    print(f"  QUERY_FILE    : {query_file}", file=sys.stderr)
    print(f"  RESULTS_FILE  : {results_file}", file=sys.stderr)
    print(f"  LOG_FILE      : {log_file}", file=sys.stderr)
    print("=" * w, file=sys.stderr)

    # Machine-readable JSON on stdout for Claude
    print(json.dumps({
        "run_id": run_id,
        "baseline_mean_s": baseline_mean,
        "original_file": str(original_file),
        "query_file": str(query_file),
        "results_file": results_file,
        "log_file": log_file,
        "branch": branch_name,
        "sha": sha,
    }, indent=2))


if __name__ == "__main__":
    main()
