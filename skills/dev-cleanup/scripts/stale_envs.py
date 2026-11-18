#!/usr/bin/env python3
"""Read-only: find big node_modules / .venv / target / bin / obj dirs in projects untouched for N days.
Deletable because they regenerate (`bun install`, `uv sync`, `cargo build`, `dotnet build`).

Usage: stale_envs.py [ROOT=$AZDO_WORK_DIR|$BMS_WORK_DIR|~/projects] [--days 30] [--min-mb 100]
"""

import argparse
import os
import subprocess
import time
from pathlib import Path

NAMES = {"node_modules", ".venv", "target", "bin", "obj", ".next", ".turbo"}
DOTNET_PROJECTS = (".csproj", ".fsproj", ".vbproj")


def is_env_dir(name: str, parent_files: list[str]) -> bool:
    """`target`, `bin` and `obj` are common names: they only count next to the manifest that makes them build output."""
    if name == "target":
        return "Cargo.toml" in parent_files
    if name in {"bin", "obj"}:
        return any(f.endswith(DOTNET_PROJECTS) for f in parent_files)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "root", nargs="?", default=os.environ.get("AZDO_WORK_DIR") or os.environ.get("BMS_WORK_DIR") or "~/projects"
    )
    ap.add_argument("--days", type=float, default=30)
    ap.add_argument("--min-mb", type=float, default=100)
    a = ap.parse_args()
    cutoff = time.time() - a.days * 86400
    hits = []
    for dp, dirs, files in os.walk(Path(a.root).expanduser()):
        keep = []
        for d in dirs:
            if d in NAMES and is_env_dir(d, files):
                p = Path(dp, d)
                if p.stat().st_mtime < cutoff:
                    mb = (
                        int(
                            (
                                subprocess.run(
                                    ["du", "-sk", str(p)], capture_output=True, text=True, check=False
                                ).stdout.split()
                                or ["0"]
                            )[0]
                        )
                        / 1024
                    )
                    if mb >= a.min_mb:
                        hits.append((mb, p))
            elif d != ".git":
                keep.append(d)
        dirs[:] = keep  # never descend into the env dirs themselves
    for mb, p in sorted(hits, reverse=True):
        print(f"{mb / 1024:6.2f} GB  {p}")
    print(f"\n{sum(m for m, _ in hits) / 1024:.1f} GB in {len(hits)} dirs untouched >{a.days:.0f}d")


if __name__ == "__main__":
    main()
