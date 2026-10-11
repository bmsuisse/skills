---
name: dev-cleanup
plugin: dev-cleanup
description: >
  Free disk space on a developer workstation: scan podman/docker storage, uv/npm/bun/pnpm/pip/cargo/gradle
  caches, app caches in ~/Library/Caches, stale git worktrees and old node_modules/.venv, show an overview
  with sizes and risk, and let the user pick what to clean. Use for "clean up my machine", "disk is full",
  "free up space", "clear caches", "podman prune", "uv cache", "stale worktrees", "remove old worktrees",
  "what is eating my disk", "need more disk space", even if the user names only one of these. Never deletes
  before the user has seen the overview and chosen.
---

# Dev workstation cleanup

Flow is always **scan, show overview, user picks, delete only the picks, report freed space**. Deleting is the
easy part; the value is a trustworthy overview, because worktrees and images can hold work the user cares about.

## 1. Scan (read-only, run in parallel, in the background if slow)

```bash
S=<this skill dir>/scripts
python3 $S/scan.py                    # caches, podman/docker, app caches: size + risk + clean command
python3 $S/worktrees.py ~/DevOps      # every git worktree: size, dirty, unpushed, locked, active, idle
python3 $S/stale_envs.py ~/DevOps     # node_modules/.venv/target untouched for 30d+
df -h ~ | tail -1                     # record free space before
```

`du` over large trees takes minutes; start all three at once and say so, rather than going silent. Add `--json`
(scan, worktrees) when you need to filter. Change the root if the user keeps repos elsewhere.

## 2. Present one overview, then ask

Merge the output into a single table sorted by size, grouped by risk, so the user decides in one reply:

| # | What | Size | Risk | Action |
|---|------|------|------|--------|

- **Safe by default**: package-manager caches, app caches, Playwright browsers, worktrees marked `safe`.
- **Needs a decision**: podman/docker (`prune -a` removes every image not in use), HuggingFace models, volumes,
  worktrees marked `review: ...` (list the reason: dirty, N unpushed, locked, active, recently touched).
- **Never offer**: worktrees with uncommitted changes or unpushed commits; locked ones; ones with an active
  process (that is another Claude session working there). Show them, but only as "kept, because ...".

Use AskUserQuestion with multiSelect over the categories when it is available; otherwise ask the user to reply
with row numbers. If the user said "clean everything safe", that authorizes the *safe* rows only.

Always end the overview with an explicit question and stop: "Remove these N worktrees (X GB) and clean rows ...?"
Even when the user's request already said "get rid of them", the list may differ from what they imagined (the
scan finds more, or fewer, than they expect), so one yes on the concrete list is cheap and removal is not undoable.

## 3. Clean only what was picked

Run the `clean` command shown by `scan.py` for each picked row. Specifics that matter:

- **Worktrees**: `git -C <repo> worktree remove <path>`, never `--force`, never `rm -rf` (that leaves dangling
  metadata). Branches stay, so the work is recoverable. Finish with `git -C <repo> worktree prune`. For 50+
  removals write the list to a file and loop in the background; each removal is slow because of node_modules.
  Re-run `worktrees.py` first if the overview is older than a few minutes: a session may have started since.
- **Podman**: the 60 GB the folder shows is the VM's raw disk file, which only grows. Compare it with
  `podman system df` (the real content, often under 10 GB) and say so in the overview, because `prune -a` alone
  frees only the reclaimable part and the Mac's free space barely moves. Space comes back via
  `podman machine ssh -- sudo fstrim -av` (non-destructive, offer it first); recreating the machine frees the rest
  but deletes all containers and volumes, so only with explicit agreement. Check `podman ps` first.
- **uv / npm / bun / pnpm / brew**: their own `cache clean` / `prune` commands, not `rm -rf`.
- Do not touch `~/Library/Caches` entries that were not listed; Apple and system caches are not ours.

## 4. Report

Print free space before and after (`df -h ~`), what was removed per row, and what was skipped and why. If a
removal failed, say which and leave it; do not escalate to `--force` without asking.

## Ideas worth suggesting after (only mention, do not do)

`docker`/`podman` auto-prune cron, `git worktree` cleanup as a habit after merging a PR, moving
`UV_CACHE_DIR`/podman machine disk to an external drive.
