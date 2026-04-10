#!/usr/bin/env python3
"""Compute a Python complexity score using AST analysis.

Score = LOC * 1  +  max_nesting_depth * 10  +  total_cyclomatic * 5
Lower is simpler.

Usage:
    python3 scripts/complexity.py --file mymodule.py
    python3 scripts/complexity.py --file mymodule.py --json
    python3 scripts/complexity.py --file mymodule.py --per-function --json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


def count_loc(source: str) -> int:
    """Count non-empty, non-comment lines."""
    lines = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines += 1
    return lines


def max_nesting_depth(tree: ast.AST) -> int:
    """Find the maximum nesting depth of control flow structures."""
    nesting_nodes = (
        ast.If, ast.For, ast.While, ast.With, ast.Try,
        ast.ExceptHandler, ast.AsyncFor, ast.AsyncWith,
    )

    def _depth(node: ast.AST, current: int) -> int:
        if isinstance(node, nesting_nodes):
            current += 1
        max_d = current
        for child in ast.iter_child_nodes(node):
            max_d = max(max_d, _depth(child, current))
        return max_d

    return _depth(tree, 0)


def cyclomatic_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Cyclomatic complexity for a single function: 1 + number of branches."""
    branch_nodes = (
        ast.If, ast.For, ast.While, ast.ExceptHandler,
        ast.With, ast.AsyncFor, ast.AsyncWith,
        ast.Assert, ast.comprehension,
    )
    branches = sum(
        1 for node in ast.walk(func_node)
        if isinstance(node, branch_nodes)
    )
    # Also count boolean operators (and/or add branches)
    bool_ops = sum(
        len(node.values) - 1
        for node in ast.walk(func_node)
        if isinstance(node, ast.BoolOp)
    )
    return 1 + branches + bool_ops


def per_function_scores(tree: ast.AST) -> list[dict]:
    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cc = cyclomatic_complexity(node)
            func_source_lines = (node.end_lineno or 0) - node.lineno + 1
            results.append({
                "function": node.name,
                "line": node.lineno,
                "cyclomatic": cc,
                "loc": func_source_lines,
            })
    return sorted(results, key=lambda x: x["cyclomatic"], reverse=True)


def score(source: str) -> dict:
    tree = ast.parse(source)
    loc = count_loc(source)
    nesting = max_nesting_depth(tree)
    funcs = per_function_scores(tree)
    total_cyclomatic = sum(f["cyclomatic"] for f in funcs) if funcs else 0
    total = loc * 1 + nesting * 10 + total_cyclomatic * 5
    return {
        "score": total,
        "loc": loc,
        "max_nesting_depth": nesting,
        "total_cyclomatic": total_cyclomatic,
        "function_count": len(funcs),
        "functions": funcs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Python complexity score (lower = simpler).")
    parser.add_argument("--file", required=True, help="Path to .py file")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--per-function", action="store_true")
    args = parser.parse_args()

    source = Path(args.file).read_text(encoding="utf-8")
    result = score(source)

    if args.as_json:
        if args.per_function:
            print(json.dumps(result, indent=2))
        else:
            out = {k: v for k, v in result.items() if k != "functions"}
            print(json.dumps(out, indent=2))
    else:
        print(f"complexity score  : {result['score']}")
        print(f"  LOC             : {result['loc']}")
        print(f"  max nesting     : {result['max_nesting_depth']}")
        print(f"  total cyclomatic: {result['total_cyclomatic']}")
        if args.per_function:
            print("\nPer-function cyclomatic complexity:")
            for fn in result["functions"]:
                flag = " ← HIGH" if fn["cyclomatic"] > 10 else ""
                print(f"  {fn['function']:30s}  cc={fn['cyclomatic']:3d}  loc={fn['loc']:3d}{flag}")


if __name__ == "__main__":
    main()
