#!/usr/bin/env python3
"""Compute a SQL complexity score for use as the optimization metric.

Score = lines * 1  +  nesting_depth * 10  +  subquery_count * 5
Lower is simpler.

Usage:
    python3 scripts/complexity.py query.sql
    python3 scripts/complexity.py --json query.sql   # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def count_lines(sql: str) -> int:
    return sum(1 for line in sql.splitlines() if line.strip())


def max_nesting_depth(sql: str) -> int:
    depth = max_depth = 0
    for ch in sql:
        if ch == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == ")":
            depth -= 1
    return max_depth


def count_subqueries(sql: str) -> int:
    # Count SELECT keywords that appear inside parentheses (i.e. not the outermost one)
    depth = 0
    count = 0
    i = 0
    tokens = re.split(r"(\(|\)|\bSELECT\b)", sql, flags=re.IGNORECASE)
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif token.upper() == "SELECT" and depth > 0:
            count += 1
    return count


def score(sql: str) -> dict:
    clean = strip_comments(sql)
    lines = count_lines(clean)
    nesting = max_nesting_depth(clean)
    subqueries = count_subqueries(clean)
    total = lines * 1 + nesting * 10 + subqueries * 5
    return {
        "score": total,
        "lines": lines,
        "max_nesting_depth": nesting,
        "subquery_count": subqueries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score SQL complexity (lower = simpler).")
    parser.add_argument("file", help="Path to .sql file")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    sql = Path(args.file).read_text(encoding="utf-8")
    result = score(sql)

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"complexity score : {result['score']}")
        print(f"  lines          : {result['lines']}")
        print(f"  nesting depth  : {result['max_nesting_depth']}")
        print(f"  subqueries     : {result['subquery_count']}")


if __name__ == "__main__":
    main()
