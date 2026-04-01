from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Hit:
    file: Path
    line: int
    rule: str
    text: str


PYTHON_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("no-hasattr", re.compile(r"\bhasattr\s*\(")),
    ("no-isinstance", re.compile(r"\bisinstance\s*\(")),
    ("broad-except", re.compile(r"\bexcept\s+Exception\b")),
    ("mutable-default-list", re.compile(r"=\s*\[\s*\]")),
    ("mutable-default-dict", re.compile(r"=\s*\{\s*\}")),
    ("optional-type", re.compile(r"\bOptional\[")),
    ("dict-any", re.compile(r"dict\[str,\s*Any\]")),
    ("getattr-escape", re.compile(r"\bgetattr\s*\(")),
    ("inline-comment", re.compile(r"(?<!['\"])#(?!.*noqa)(?!.*type:)(?!\s*$)")),
]

TYPESCRIPT_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("no-any", re.compile(r":\s*any\b")),
    ("non-null-assertion", re.compile(r"[^!]!\.")),
    ("inline-comment", re.compile(r"(?<!:)//(?!\s*(eslint|ts-ignore|TODO|@))")),
]


def git_tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [root / p for p in result.stdout.splitlines() if p.strip()]


def scan_file(path: Path) -> list[Hit]:
    rules = PYTHON_RULES if path.suffix == ".py" else TYPESCRIPT_RULES
    hits: list[Hit] = []
    for i, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
        stripped = line.strip()
        for name, pattern in rules:
            if pattern.search(stripped):
                hits.append(Hit(file=path, line=i, rule=name, text=stripped[:80]))
    return hits


def scan(root: Path, extensions: list[str]) -> list[Hit]:
    exts = {e if e.startswith(".") else f".{e}" for e in extensions}
    files = [f for f in git_tracked_files(root) if f.is_file() and f.suffix in exts]
    return [hit for path in files for hit in scan_file(path)]


def print_report(hits: list[Hit], root: Path) -> None:
    if not hits:
        print("No violations found.")
        return

    by_rule: dict[str, list[Hit]] = {}
    for h in hits:
        by_rule.setdefault(h.rule, []).append(h)

    for rule, rule_hits in sorted(by_rule.items()):
        print(f"\n● {rule} ({len(rule_hits)})")
        for h in rule_hits:
            rel = h.file.relative_to(root)
            print(f"  {rel}:{h.line}  {h.text}")

    print(f"\n{len(hits)} violation(s) across {len(by_rule)} rule(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan for coding guideline violations")
    parser.add_argument("root", nargs="?", default=".", help="Repo root (default: cwd)")
    parser.add_argument(
        "-e", "--ext", nargs="*", default=["py", "ts"], help="Extensions to scan (default: py ts)"
    )
    parser.add_argument("--rule", help="Filter to a single rule name")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    hits = scan(root, args.ext)
    if args.rule:
        hits = [h for h in hits if h.rule == args.rule]
    print_report(hits, root)


if __name__ == "__main__":
    main()
