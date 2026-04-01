from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileStats:
    path: Path
    lines: int


def git_tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [root / p for p in result.stdout.splitlines() if p.strip()]


def count_lines(path: Path) -> FileStats:
    return FileStats(path=path, lines=path.read_text(errors="ignore").count("\n"))


def filter_by_extensions(files: list[Path], extensions: list[str]) -> list[Path]:
    exts = {e if e.startswith(".") else f".{e}" for e in extensions}
    return [f for f in files if f.suffix in exts]


def collect_stats(root: Path, extensions: list[str] | None) -> list[FileStats]:
    files = git_tracked_files(root)
    if extensions:
        files = filter_by_extensions(files, extensions)
    return sorted(
        [count_lines(f) for f in files if f.is_file()],
        key=lambda s: s.lines,
        reverse=True,
    )


def print_table(stats: list[FileStats], root: Path, limit: int | None) -> None:
    rows = stats[:limit] if limit else stats
    total = sum(s.lines for s in stats)
    width = max((len(str(s.path.relative_to(root))) for s in rows), default=40)

    print(f"{'File':<{width}}  Lines")
    print("-" * (width + 8))
    for s in rows:
        print(f"{str(s.path.relative_to(root)):<{width}}  {s.lines:>6}")
    print("-" * (width + 8))
    print(f"{'Total':<{width}}  {total:>6}  ({len(stats)} files)")

    over_limit = [s for s in stats if s.lines > 500]
    if over_limit:
        print(f"\n⚠️  {len(over_limit)} file(s) exceed 500 lines:")
        for s in over_limit:
            print(f"  {s.path.relative_to(root)}  ({s.lines} lines)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lines of code per file in a git repo")
    parser.add_argument("root", nargs="?", default=".", help="Repo root (default: cwd)")
    parser.add_argument("-e", "--ext", nargs="*", help="Filter by extensions, e.g. py ts")
    parser.add_argument("-n", "--top", type=int, default=None, help="Show only top N files")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    stats = collect_stats(root, args.ext)
    print_table(stats, root, args.top)


if __name__ == "__main__":
    main()
