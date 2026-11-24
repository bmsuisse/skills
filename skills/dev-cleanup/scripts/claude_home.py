#!/usr/bin/env python3
"""Claude Code leftovers: old plugin versions in ~/.claude/plugins/cache and stale `<repo>/.claude/worktrees/*`
dirs. Read-only unless `--delete-plugins` is given.

Claude Code installs every plugin update into a new `cache/<marketplace>/<plugin>/<version>/` dir and never
removes the old ones. A version is `stale` when no entry in installed_plugins.json points at it and no live
process is registered in its `.in_use/<pid>` files (`.orphaned_at` is Claude's own marker, shown as the age).

Worktrees that git still knows are covered by `bdt cleanup inspect|worktrees|worktree`. This script lists only
dirs under `.claude/worktrees` that git does NOT know (`orphan`: gitdir gone), which bdt cannot see.

Usage: claude_home.py [ROOT=$AZDO_WORK_DIR|$BMS_WORK_DIR|~/projects] [--json] [--depth 2] [--delete-plugins]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CLAUDE = Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser()
PLUGINS = CLAUDE / "plugins"


def du_mb(p: Path) -> float:
    try:
        out = subprocess.run(["du", "-sk", str(p)], capture_output=True, text=True, timeout=300).stdout
        return int(out.split()[0]) / 1024
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return 0.0


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def plugin_versions() -> list[dict]:
    """Every cached plugin version that is not installed anywhere, with a verdict."""
    try:
        installed = json.loads((PLUGINS / "installed_plugins.json").read_text())["plugins"]
    except (OSError, ValueError, KeyError):
        return []  # without the index we cannot tell what is installed: report nothing rather than guess
    keep = {Path(e["installPath"]).resolve() for entries in installed.values() for e in entries}
    rows = []
    for ver in (PLUGINS / "cache").glob("*/*/*"):
        if not ver.is_dir() or ver.resolve() in keep:
            continue
        in_use = ver / ".in_use"
        live = (
            [p.name for p in in_use.iterdir() if p.name.isdigit() and pid_alive(int(p.name))] if in_use.is_dir() else []
        )
        marker = ver / ".orphaned_at"
        age_d = (time.time() - int(marker.read_text().strip() or 0) / 1000) / 86400 if marker.is_file() else None
        rows.append(
            dict(
                path=str(ver),
                plugin=f"{ver.parent.name}@{ver.parent.parent.name}",
                version=ver.name,
                orphaned_days=round(age_d) if age_d is not None else None,
                live_pids=live,
                size_mb=round(du_mb(ver)),
                verdict="review: used by a live process" if live else "stale",
            )
        )
    return sorted(rows, key=lambda r: -r["size_mb"])


def registered_worktrees(repo: Path) -> set[Path]:
    try:
        out = subprocess.run(
            ["git", "worktree", "list", "--porcelain"], cwd=repo, capture_output=True, text=True, timeout=60
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {Path(line.split(" ", 1)[1]).resolve() for line in out.splitlines() if line.startswith("worktree ")}


def unregistered_claude_worktrees(root: Path, depth: int) -> list[dict]:
    rows, stack = [], [(root, 0)]
    while stack:
        d, n = stack.pop()
        if (d / ".git").is_dir():
            wt_dir = d / ".claude" / "worktrees"
            known = registered_worktrees(d) if wt_dir.is_dir() else set()
            for w in sorted(wt_dir.iterdir()) if wt_dir.is_dir() else []:
                if not w.is_dir() or w.resolve() in known:
                    continue
                gitfile = w / ".git"
                ptr = gitfile.read_text().strip().removeprefix("gitdir:").strip() if gitfile.is_file() else ""
                if ptr and Path(ptr).exists():
                    # another clone's admin dir is still alive: that clone owns it (bdt cleanup inspect there)
                    verdict, why = "review: owned by another clone", f"gitdir {ptr}"
                else:
                    verdict, why = "orphan", "gitdir missing" if ptr else "no .git file"
                rows.append(
                    dict(
                        path=str(w),
                        repo=str(d),
                        why=why,
                        size_mb=round(du_mb(w)),
                        idle_days=round((time.time() - w.stat().st_mtime) / 86400),
                        verdict=verdict,
                    )
                )
            continue
        if n < depth:
            try:
                stack += [(c, n + 1) for c in d.iterdir() if c.is_dir() and not c.name.startswith(".")]
            except PermissionError:
                pass
    return sorted(rows, key=lambda r: -r["size_mb"])


def delete_stale_plugins(rows: list[dict]) -> None:
    freed = 0
    for r in rows:
        if r["verdict"] == "stale":
            shutil.rmtree(r["path"], ignore_errors=True)
            freed += r["size_mb"]
    for p in sorted((PLUGINS / "cache").glob("*/*")):  # plugin dirs left with no version at all
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    print(f"removed stale plugin versions, freed about {freed / 1024:.1f} GB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "root", nargs="?", default=os.environ.get("AZDO_WORK_DIR") or os.environ.get("BMS_WORK_DIR") or "~/projects"
    )
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--delete-plugins", action="store_true", help="remove every `stale` plugin version (after the user confirmed)"
    )
    a = ap.parse_args()

    plugins = plugin_versions()
    if a.delete_plugins:
        delete_stale_plugins(plugins)
        return
    wts = unregistered_claude_worktrees(Path(a.root).expanduser(), a.depth)
    if a.json:
        json.dump(dict(plugins=plugins, worktrees=wts), sys.stdout, indent=2)
        return

    stale = [r for r in plugins if r["verdict"] == "stale"]
    print(
        f"Plugin cache: {len(stale)} stale versions ({sum(r['size_mb'] for r in stale) / 1024:.1f} GB) in {PLUGINS / 'cache'}"
    )
    for r in plugins:
        age = f"orphaned {r['orphaned_days']}d ago" if r["orphaned_days"] is not None else "not installed"
        print(f"{r['size_mb'] / 1024:6.2f} GB  {r['plugin']:<45} {r['version']:<14} {age}; {r['verdict']}")
    orphans = [r for r in wts if r["verdict"] == "orphan"]
    print(
        f"\n.claude/worktrees dirs unknown to git: {len(orphans)} orphan ({sum(r['size_mb'] for r in orphans) / 1024:.1f} GB), {len(wts) - len(orphans)} to review"
    )
    for r in wts:
        print(
            f"{r['size_mb'] / 1024:6.2f} GB  {Path(r['repo']).name}: {Path(r['path']).name:<35} {r['verdict']} ({r['why']}, touched {r['idle_days']}d ago)\n          {r['path']}"
        )


if __name__ == "__main__":
    main()
