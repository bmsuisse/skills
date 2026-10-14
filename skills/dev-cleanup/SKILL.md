---
name: dev-cleanup
plugin: dev-cleanup
description: >
  Free disk space on a developer workstation: scan podman/docker storage, uv/npm/bun/pnpm/pip/cargo/gradle
  caches, app caches in ~/Library/Caches, stale git worktrees and old node_modules/.venv, show an overview
  with sizes and risk, and let the user pick what to clean. Use for "clean up my machine", "disk is full",
  "free up space", "clear caches", "podman prune", "uv cache", "stale worktrees", "remove old worktrees",
  "what is eating my disk", "need more disk space", "orphaned test databases", "drop old pgdevkit DBs", even
  if the user names only one of these. Uses `bdt cleanup` for merged worktrees and their pgdevkit test DBs.
  Never deletes before the user has seen the overview and chosen.
---

# Dev workstation cleanup

Flow is always **scan, show overview, user picks, delete only the picks, report freed space**. Deleting is the
easy part; the value is a trustworthy overview, because worktrees and images can hold work the user cares about.

Worktrees and their Postgres test databases go through **`bdt cleanup`** (bmsdna-devtools,
`uv tool install bmsdna-devtools`; check with `bdt cleanup --help`). It knows which worktrees are fully merged and
drops the pgdevkit test DB(s) that belong to them, which `git worktree remove` alone leaves behind. Everything
else (caches, podman, stale envs, unmerged worktrees) stays with the scripts below.

## 1. Scan (read-only, run in parallel, in the background if slow)

```bash
S=<this skill dir>/scripts
python3 $S/scan.py                    # caches, podman/docker, app caches: size + risk + clean command
bdt cleanup worktrees ~/DevOps        # DRY RUN: worktrees fully merged into origin/main|test (+ their test DBs)
bdt cleanup orphaned-dbs ~/DevOps     # DRY RUN: pgdevkit test DBs whose worktree is already gone
python3 $S/worktrees.py ~/DevOps      # every git worktree: size, dirty, unpushed, locked, active, idle
python3 $S/stale_envs.py ~/DevOps     # node_modules/.venv/target untouched for 30d+
df -h ~ | tail -1                     # record free space before
```

Both `bdt cleanup` commands only print what they would remove until `--yes` is passed, so running them in the
scan step is safe. They need the Postgres of the pgdevkit test container reachable (`localhost:54322` by
default, `--pg-host/--pg-port/--pg-user` or `PGHOST/PGPORT/PGUSER` to change); if it is down, say so and fall
back to `worktrees.py` for the worktree rows.

`du` over large trees takes minutes; start them all at once and say so, rather than going silent. Add `--json`
(scan, worktrees) when you need to filter. Change the root if the user keeps repos elsewhere.

## 2. Present one overview, then ask

Merge the output into a single table (one row per repo for `bdt cleanup` results, with the worktree count and
whether test DBs go with them) sorted by size, grouped by risk, so the user decides in one reply:

| # | What | Size | Risk | Action |
|---|------|------|------|--------|

- **Safe by default**: package-manager caches, app caches, Playwright browsers, worktrees listed by
  `bdt cleanup worktrees` (merged), orphaned test DBs from `bdt cleanup orphaned-dbs` that are not flagged
  "caution".
- **Needs a decision**: podman/docker (`prune -a` removes every image not in use), HuggingFace models, volumes,
  worktrees marked `review: ...` by `worktrees.py` (list the reason: dirty, N unpushed, locked, active, recently
  touched), orphaned DBs flagged as a possible standing reference DB (`--include-caution`, verify first).
- **Never offer**: worktrees with uncommitted changes or unpushed commits; locked ones; ones with an active
  process (that is another Claude session working there). Show them, but only as "kept, because ...".

Use AskUserQuestion with multiSelect over the categories when it is available; otherwise ask the user to reply
with row numbers. If the user said "clean everything safe", that authorizes the *safe* rows only.

Always end the overview with an explicit question and stop: "Remove these N worktrees (X GB) and clean rows ...?"
Even when the user's request already said "get rid of them", the list may differ from what they imagined (the
scan finds more, or fewer, than they expect), so one yes on the concrete list is cheap and removal is not undoable.

## 3. Clean only what was picked

Run the `clean` command shown by `scan.py` for each picked row. Specifics that matter:

- **Merged worktrees + their test DBs**: `bdt cleanup worktrees <root> --yes` after the user confirmed the
  dry-run list. It removes every merged worktree under the root, so re-run the dry run right before `--yes` if the
  overview is older than a few minutes, and drop entries the user did not pick by running it on a narrower
  `<root>` (one repo) instead. Add `--keep-dbs` if the user wants to keep the databases. A worktree you just
  created from `origin/main` with no commits yet also counts as "merged", so never run it from, or on a root
  containing, the worktree you are working in unless the user wants that one gone too.
- **Orphaned test DBs**: `bdt cleanup orphaned-dbs <root> --yes`. Leave out `--include-caution` unless the user
  checked the flagged DBs. A non-local `--pg-host` makes bdt ask for a typed `yes` that no flag bypasses; leave
  that prompt to the user, never work around it.
- **One specific worktree** (user names it, merged or not): from inside it, `bdt cleanup worktree --confirm`
  (add `--keep-db` to keep its DB); it refuses main/test, locked and dirty worktrees. `bdt cleanup db --confirm`
  drops only that worktree's test DB(s) and keeps the worktree.
- **Unmerged worktrees** (only the ones `worktrees.py` marks `safe`, after the user picked them):
  `bdt cleanup worktree --confirm` from inside each, or `git -C <repo> worktree remove <path>` if bdt is not
  installed, never `--force`, never `rm -rf` (that leaves dangling metadata and the test DB). Branches stay, so
  the work is recoverable. Finish with `git -C <repo> worktree prune`. For 50+ removals write the list to a file
  and loop in the background; each removal is slow because of node_modules. Re-run `worktrees.py` first if the
  overview is older than a few minutes: a session may have started since.
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

`docker`/`podman` auto-prune cron, `bdt cleanup worktree --confirm` as a habit right after a PR merges, moving
`UV_CACHE_DIR`/podman machine disk to an external drive.
