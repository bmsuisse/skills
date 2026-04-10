#!/usr/bin/env python3
"""Run ruff (lint + style) and ty (type checking) on a Python file.

Returns structured JSON with violation counts and details.

Usage:
    python3 scripts/check_quality.py --file mymodule.py
    python3 scripts/check_quality.py --file mymodule.py --json
    python3 scripts/check_quality.py --file mymodule.py --fix   # auto-fix ruff violations
"""
from __future__ import annotations

import argparse
import json
import subprocess


def run_ruff(file: str, fix: bool = False) -> dict:
    cmd = ["ruff", "check", file, "--output-format=json"]
    if fix:
        cmd.append("--fix")

    result = subprocess.run(cmd, capture_output=True, text=True)

    violations = []
    try:
        raw = json.loads(result.stdout) if result.stdout.strip() else []
        for v in raw:
            violations.append({
                "code": v.get("code", ""),
                "message": v.get("message", ""),
                "line": v.get("location", {}).get("row", 0),
                "col": v.get("location", {}).get("column", 0),
                "fixable": v.get("fix") is not None,
            })
    except json.JSONDecodeError:
        pass

    fixable_count = sum(1 for v in violations if v["fixable"])
    by_code: dict[str, int] = {}
    for v in violations:
        by_code[v["code"]] = by_code.get(v["code"], 0) + 1

    return {
        "count": len(violations),
        "fixable_count": fixable_count,
        "by_code": dict(sorted(by_code.items(), key=lambda x: -x[1])),
        "violations": violations,
        "returncode": result.returncode,
    }


def run_ty(file: str) -> dict:
    result = subprocess.run(
        ["ty", "check", file],
        capture_output=True,
        text=True,
    )

    errors = []
    # ty outputs lines like: path/to/file.py:LINE:COL: error [rule] message
    for line in (result.stdout + result.stderr).splitlines():
        line = line.strip()
        if not line or line.startswith("Found"):
            continue
        # Parse "file.py:10:5: error [rule] message"
        parts = line.split(":", 3)
        if len(parts) >= 4:
            try:
                lineno = int(parts[1])
                col = int(parts[2])
                rest = parts[3].strip()
                errors.append({"line": lineno, "col": col, "message": rest})
            except ValueError:
                errors.append({"line": 0, "col": 0, "message": line})
        elif "error" in line.lower() or "warning" in line.lower():
            errors.append({"line": 0, "col": 0, "message": line})

    return {
        "count": len(errors),
        "errors": errors,
        "returncode": result.returncode,
    }


def check(file: str, fix: bool = False) -> dict:
    ruff = run_ruff(file, fix=fix)
    ty = run_ty(file)
    total = ruff["count"] + ty["count"]
    return {
        "file": file,
        "total_issues": total,
        "ruff": ruff,
        "ty": ty,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ruff + ty quality checks.")
    parser.add_argument("--file", required=True, help="Path to .py file")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--fix", action="store_true", help="Auto-fix ruff violations")
    args = parser.parse_args()

    result = check(args.file, fix=args.fix)

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        r = result["ruff"]
        t = result["ty"]
        print(f"ruff: {r['count']} violations ({r['fixable_count']} auto-fixable)")
        if r["by_code"]:
            for code, n in list(r["by_code"].items())[:10]:
                print(f"  {code}: {n}")
        print(f"ty:   {t['count']} errors")
        for e in t["errors"][:10]:
            loc = f":{e['line']}:{e['col']}" if e["line"] else ""
            print(f"  {loc} {e['message']}")
        print(f"\nTotal: {result['total_issues']} issues")


if __name__ == "__main__":
    main()
