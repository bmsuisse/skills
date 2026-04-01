from __future__ import annotations

import argparse
import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FunctionInfo:
    file: Path
    name: str
    start: int
    lines: int


def git_tracked_files(root: Path, extensions: list[str]) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    exts = {e if e.startswith(".") else f".{e}" for e in extensions}
    return [root / p for p in result.stdout.splitlines() if Path(p).suffix in exts]


def extract_functions(path: Path) -> list[FunctionInfo]:
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except SyntaxError:
        return []

    results: list[FunctionInfo] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        results.append(
            FunctionInfo(
                file=path,
                name=node.name,
                start=node.lineno,
                lines=end - node.lineno + 1,
            )
        )
    return results


def print_report(hits: list[FunctionInfo], root: Path, threshold: int) -> None:
    if not hits:
        print(f"No functions over {threshold} lines found.")
        return

    width = max(len(str(h.file.relative_to(root))) for h in hits)
    print(f"{'File':<{width}}  {'Function':<40}  Line  Lines")
    print("-" * (width + 52))
    for h in hits:
        rel = str(h.file.relative_to(root))
        print(f"{rel:<{width}}  {h.name:<40}  {h.start:>4}  {h.lines:>5}")
    print(f"\n{len(hits)} function(s) exceed {threshold} lines.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find functions over N lines")
    parser.add_argument("root", nargs="?", default=".", help="Repo root (default: cwd)")
    parser.add_argument("-n", "--max-lines", type=int, default=20, help="Line threshold (default: 20)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    files = git_tracked_files(root, ["py"])
    functions = [f for path in files for f in extract_functions(path)]
    hits = sorted(
        [f for f in functions if f.lines > args.max_lines],
        key=lambda f: f.lines,
        reverse=True,
    )
    print_report(hits, root, args.max_lines)


if __name__ == "__main__":
    main()
