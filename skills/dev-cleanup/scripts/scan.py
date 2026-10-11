#!/usr/bin/env python3
"""Read-only disk-usage overview of dev-workstation caches. Deletes nothing.

Usage: scan.py [--json] [--min-mb 50]
Prints one row per cleanable category: size, what it is, the command that cleans it.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOME = Path.home()


def du_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    try:
        out = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True, timeout=300).stdout
        return int(out.split()[0]) / 1024
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        return 0.0


def cmd_out(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def cache_dir(tool: str, *args: str, fallback: Path) -> Path:
    if shutil.which(tool):
        out = cmd_out(tool, *args)
        if out:
            return Path(out.splitlines()[-1])
    return fallback


def podman_real_gb() -> str:
    """`podman system df` shows real content; the folder size is the VM's raw disk, which never shrinks by itself."""
    out = cmd_out("podman", "system", "df", "--format", "{{.Type}}: {{.Size}} ({{.Reclaimable}} reclaimable)")
    return " | ".join(out.splitlines()) if out else "podman not reachable (start `podman machine`) - real content unknown"


def categories() -> list[dict]:
    """Each: id, label, path (sized with du), clean (command to run after user confirms), risk."""
    c = [
        dict(id="podman", label="Podman VM disk file; real content inside: " + podman_real_gb(),
             path=HOME / ".local/share/containers",
             clean="podman machine ssh -- sudo fstrim -av  (shrinks the VM disk file), then podman system prune -a -f; --volumes only if user agrees",
             risk="medium: prune -a removes every image not used by a running container; folder size is the VM disk, real gain is often much smaller"),
        dict(id="docker", label="Docker Desktop data", path=HOME / "Library/Containers/com.docker.docker",
             clean="docker system prune -a -f", risk="medium"),
        dict(id="uv", label="uv cache", path=cache_dir("uv", "cache", "dir", fallback=HOME / ".cache/uv"),
             clean="uv cache clean", risk="low: re-downloaded on next sync"),
        dict(id="npm", label="npm cache", path=HOME / ".npm", clean="npm cache clean --force", risk="low"),
        dict(id="bun", label="bun install cache", path=HOME / ".bun/install/cache",
             clean="bun pm cache rm", risk="low"),
        dict(id="pnpm", label="pnpm store", path=HOME / "Library/pnpm/store",
             clean="pnpm store prune", risk="low"),
        dict(id="pip", label="pip cache", path=HOME / "Library/Caches/pip",
             clean="rm -rf ~/Library/Caches/pip", risk="low"),
        dict(id="cargo", label="cargo registry + git checkouts", path=HOME / ".cargo/registry",
             clean="rm -rf ~/.cargo/registry/cache ~/.cargo/git/checkouts", risk="low: re-downloaded on build"),
        dict(id="gradle", label="gradle caches", path=HOME / ".gradle/caches",
             clean="rm -rf ~/.gradle/caches", risk="low: slow next build"),
        dict(id="huggingface", label="HuggingFace model cache", path=HOME / ".cache/huggingface",
             clean="rm -rf ~/.cache/huggingface/<model>   # list models first, they can be many GB",
             risk="medium: models must be re-downloaded"),
        dict(id="playwright", label="Playwright browsers", path=HOME / "Library/Caches/ms-playwright",
             clean="rm -rf ~/Library/Caches/ms-playwright", risk="low: `playwright install` restores"),
        dict(id="homebrew", label="Homebrew downloads", path=Path(cmd_out("brew", "--cache") or HOME / "Library/Caches/Homebrew"),
             clean="brew cleanup --prune=all", risk="low"),
        dict(id="xcode-derived", label="Xcode DerivedData", path=HOME / "Library/Developer/Xcode/DerivedData",
             clean="rm -rf ~/Library/Developer/Xcode/DerivedData", risk="low: rebuilt"),
        dict(id="xcode-sim", label="Xcode simulators (unavailable)", path=HOME / "Library/Developer/CoreSimulator",
             clean="xcrun simctl delete unavailable", risk="low"),
        dict(id="trash", label="Trash", path=HOME / ".Trash", clean="empty Trash (user does it in Finder)", risk="check first"),
        dict(id="logs", label="~/Library/Logs", path=HOME / "Library/Logs", clean="rm -rf ~/Library/Logs/*", risk="low"),
    ]
    return c


def library_caches() -> list[dict]:
    """Largest app caches under ~/Library/Caches, as separate rows so user can pick."""
    root = HOME / "Library/Caches"
    if not root.is_dir():
        return []
    dirs = [d for d in root.iterdir() if d.is_dir() and d.name not in {"pip", "ms-playwright", "Homebrew"}]
    with ThreadPoolExecutor(8) as ex:
        sizes = list(ex.map(du_mb, dirs))
    return [dict(id=f"appcache:{d.name}", label=f"App cache {d.name}", path=d, size_mb=s,
                 clean=f"rm -rf '{d}'", risk="low: app rebuilds it")
            for d, s in zip(dirs, sizes)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-mb", type=float, default=50)
    a = ap.parse_args()

    cats = categories()
    with ThreadPoolExecutor(8) as ex:
        for cat, s in zip(cats, ex.map(lambda c: du_mb(c["path"]), cats)):
            cat["size_mb"] = s
    cats += library_caches()
    rows = sorted((c for c in cats if c["size_mb"] >= a.min_mb), key=lambda c: -c["size_mb"])
    for r in rows:
        r["path"] = str(r["path"])

    free = shutil.disk_usage(HOME).free / 2**30
    if a.json:
        json.dump(dict(free_gb=round(free, 1), rows=rows), sys.stdout, indent=2)
        return
    print(f"Free disk: {free:.1f} GB   (rows >= {a.min_mb:.0f} MB, nothing deleted)\n")
    print(f"{'GB':>6}  {'id':<22} what / risk\n")
    for r in rows:
        print(f"{r['size_mb'] / 1024:6.1f}  {r['id']:<22} {r['label']}  [{r['risk']}]")
    print(f"\n{sum(r['size_mb'] for r in rows) / 1024:6.1f}  total reclaimable candidates")
    print("\nNot covered here: git worktrees -> scripts/worktrees.py ; stale node_modules/.venv -> scripts/stale_envs.py")


if __name__ == "__main__":
    main()
