#!/usr/bin/env python3
"""Read-only: find big node_modules / .venv / target dirs in projects untouched for N days.
Deletable because they regenerate (`bun install`, `uv sync`, `cargo build`).

Usage: stale_envs.py [ROOT=~/DevOps] [--days 30] [--min-mb 100]
"""
import argparse
import os
import subprocess
import time
from pathlib import Path

NAMES = {"node_modules", ".venv", "target", ".next", ".turbo"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="~/DevOps")
    ap.add_argument("--days", type=float, default=30)
    ap.add_argument("--min-mb", type=float, default=100)
    a = ap.parse_args()
    cutoff = time.time() - a.days * 86400
    hits = []
    for dp, dirs, _ in os.walk(Path(a.root).expanduser()):
        keep = []
        for d in dirs:
            if d in NAMES:
                p = Path(dp, d)
                # `target` only counts next to a Cargo.toml (else it may be real data)
                if d == "target" and not Path(dp, "Cargo.toml").exists():
                    continue
                if p.stat().st_mtime < cutoff:
                    mb = int((subprocess.run(["du", "-sk", str(p)], capture_output=True, text=True).stdout.split() or ["0"])[0]) / 1024
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
