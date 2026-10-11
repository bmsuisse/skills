#!/usr/bin/env python3
"""Read-only report of git worktrees under a root: size, dirty, unpushed, locked, active, age.
Deletes nothing. Verdict `safe` = clean, nothing unpushed, not locked, no process inside, idle >= --idle-hours.

Usage: worktrees.py [ROOT=~/DevOps] [--idle-hours 24] [--json] [--depth 2]
Remove a `safe` row with:  git -C <main_repo> worktree remove <path>   (branch stays; never --force).
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def run(*cmd: str, cwd: str | None = None) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def main_repos(root: Path, depth: int) -> list[Path]:
    """Dirs whose `.git` is a directory (a `.git` file marks a worktree, not a main repo)."""
    found, stack = [], [(root, 0)]
    while stack:
        d, n = stack.pop()
        if (d / ".git").is_dir():
            found.append(d)
            continue
        if n < depth:
            try:
                stack += [(c, n + 1) for c in d.iterdir() if c.is_dir() and not c.name.startswith(".")]
            except PermissionError:
                pass
    return found


def worktrees_of(repo: Path) -> list[dict]:
    out, wts, cur = run("git", "worktree", "list", "--porcelain", cwd=str(repo)), [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if cur and Path(cur["worktree"]) != repo:
                wts.append(dict(path=cur["worktree"], repo=str(repo), branch=cur.get("branch", "(detached)").removeprefix("refs/heads/"),
                                locked="locked" in cur, prunable="prunable" in cur))
            cur = {}
        else:
            k, _, v = line.partition(" ")
            cur[k] = v
    return wts


def active_cwds() -> list[str]:
    """Working dirs of all running processes, one lsof call (per-worktree lsof +D is far too slow)."""
    return [l[1:] for l in run("lsof", "-w", "-d", "cwd", "-Fn").splitlines() if l.startswith("n/")]


def inspect(wt: dict, cwds: list[str], idle_hours: float) -> dict:
    p = wt["path"]
    if not Path(p).is_dir():
        return {**wt, "size_mb": 0, "dirty": False, "unpushed": 0, "active": False, "idle_h": 0, "verdict": "prunable (dir missing): git worktree prune"}
    size = int((run("du", "-sk", p).split() or ["0"])[0]) / 1024
    dirty = bool(run("git", "status", "--porcelain", cwd=p).strip())
    # commits reachable from HEAD but from no remote branch: lost if the worktree+branch were deleted
    unpushed = len(run("git", "log", "--oneline", "HEAD", "--not", "--remotes", cwd=p).splitlines())
    active = any(c == p or c.startswith(p + "/") for c in cwds)
    last_commit = int(run("git", "log", "-1", "--format=%ct", cwd=p).strip() or 0)
    mt = max([Path(p).stat().st_mtime, last_commit] + [f.stat().st_mtime for f in Path(p).glob("*") if f.name != "node_modules" and f.exists()][:200])
    idle_h = (time.time() - mt) / 3600
    why = [w for w, bad in [("dirty", dirty), (f"{unpushed} unpushed", unpushed), ("locked", wt["locked"]),
                            ("active process", active), (f"touched {idle_h:.0f}h ago", idle_h < idle_hours)] if bad]
    return {**wt, "size_mb": round(size), "dirty": dirty, "unpushed": unpushed, "active": active,
            "idle_h": round(idle_h), "verdict": "safe" if not why else "review: " + ", ".join(why)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="~/DevOps")
    ap.add_argument("--idle-hours", type=float, default=24)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).expanduser()

    wts = [w for r in main_repos(root, a.depth) for w in worktrees_of(r)]
    cwds = active_cwds()
    with ThreadPoolExecutor(8) as ex:
        rows = sorted(ex.map(lambda w: inspect(w, cwds, a.idle_hours), wts), key=lambda r: -r["size_mb"])
    if a.json:
        json.dump(rows, sys.stdout, indent=2)
        return
    safe = [r for r in rows if r["verdict"] == "safe"]
    print(f"{len(rows)} worktrees under {root}: {len(safe)} safe ({sum(r['size_mb'] for r in safe) / 1024:.1f} GB), "
          f"{len(rows) - len(safe)} need review\n")
    for r in rows:
        print(f"{r['size_mb'] / 1024:6.2f} GB  {Path(r['repo']).name}:{r['branch']:<35} {r['verdict']}\n          {r['path']}")


if __name__ == "__main__":
    main()
