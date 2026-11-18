---
name: dev-cleanup
plugin: dev-cleanup
description: >
  Free disk space on a developer workstation: scan podman/docker storage, uv/npm/bun/pnpm/pip/cargo/NuGet/gradle
  caches, app caches in ~/Library/Caches, stale git worktrees and old node_modules/.venv/target/bin/obj, show an overview
  with sizes and risk, and let the user pick what to clean. Use for "clean up my machine", "disk is full",
  "free up space", "clear caches", "podman prune", "uv cache", "stale worktrees", "remove old worktrees",
  "what is eating my disk", "need more disk space", "orphaned test databases", "drop old pgdevkit DBs", even
  if the user names only one of these. Uses `bdt cleanup` for merged worktrees and their pgdevkit test DBs.
  Never deletes before the user has seen the overview and chosen.
---

# Dev workstation cleanup

Flow is always **scan, show overview, user picks, delete only the picks, report freed space**. Deleting is the
easy part; the value is a trustworthy overview, because worktrees and images can hold work the user cares about.

Everything goes through **`bdt cleanup`** (bmsdna-devtools >= 1.4, `uv tool upgrade bmsdna-devtools`; check with
`bdt cleanup --help`). Read-only reports: `caches`, `stale-envs`, `inspect`. Removal: `worktrees` knows which
worktrees are fully merged and drops the pgdevkit test DB(s) that belong to them, which `git worktree remove` alone
leaves behind.

## 1. Scan (read-only, run in parallel, in the background if slow)

```bash
# repo root = the work dir `bdt find-repo` uses, so every tool scans the same tree
ROOT="${AZDO_WORK_DIR:-${BMS_WORK_DIR:-$HOME/projects}}"
bdt cleanup caches                   # caches, podman/docker, app caches: size + risk + clean command
bdt cleanup worktrees "$ROOT"        # DRY RUN: worktrees fully merged into origin/main|test|dev, or local main|test|dev if no remote (+ their DBs)
bdt cleanup orphaned-dbs "$ROOT"     # DRY RUN: pgdevkit test DBs whose worktree is already gone
bdt cleanup inspect "$ROOT"          # every git worktree: size, dirty, unpushed, locked, active, idle
bdt cleanup stale-envs "$ROOT"       # node_modules/.venv/target/bin/obj untouched for 30d+
df -h ~ | tail -1                    # record free space before
```

`caches`, `inspect` and `stale-envs` only read. Both `bdt cleanup worktrees` and `orphaned-dbs` only print what they
would remove until `--yes` is passed, so running them in the scan step is safe. The two DB-aware ones need the
Postgres of the pgdevkit test container reachable (`localhost:54322` by default, `--pg-host/--pg-port/--pg-user` or
`PGHOST/PGPORT/PGUSER` to change); if it is down, say so and use `inspect` for the worktree rows.

`du` over large trees takes minutes; start them all at once and say so, rather than going silent. Add `--json` to
`caches`, `stale-envs` and `inspect` when you need to filter. `ROOT` follows `AZDO_WORK_DIR`/`BMS_WORK_DIR` (same as
`bdt find-repo`, default `~/projects`); change it only if the user keeps repos elsewhere.

## 2. Present one overview, then ask

Merge the output into a single table (one row per repo for `bdt cleanup` results, with the worktree count and
whether test DBs go with them) sorted by size, grouped by risk, so the user decides in one reply:

| # | What | Size | Risk | Action |
|---|------|------|------|--------|

- **Safe by default**: package-manager caches, app caches, Playwright browsers, worktrees listed by
  `bdt cleanup worktrees` (merged), orphaned test DBs from `bdt cleanup orphaned-dbs` that are not flagged
  "caution".
- **Needs a decision**: podman/docker (`prune -a` removes every image not in use), HuggingFace models, volumes,
  worktrees marked `review: ...` by `bdt cleanup inspect` (list the reason: dirty, N unpushed, locked, active, recently
  touched), orphaned DBs flagged as a possible standing reference DB (`--include-caution`, verify first).
- **Never offer**: worktrees with uncommitted changes or unpushed commits; locked ones; ones with an active
  process (that is another Claude session working there). Show them, but only as "kept, because ...".

Use AskUserQuestion with multiSelect over the categories when it is available; otherwise ask the user to reply
with row numbers. If the user said "clean everything safe", that authorizes the *safe* rows only.

Always end the overview with an explicit question and stop: "Remove these N worktrees (X GB) and clean rows ...?"
Even when the user's request already said "get rid of them", the list may differ from what they imagined (the
scan finds more, or fewer, than they expect), so one yes on the concrete list is cheap and removal is not undoable.

## 3. Clean only what was picked

Run the `clean` command shown by `bdt cleanup caches` for each picked row. Specifics that matter:

- **Merged worktrees + their test DBs**: `bdt cleanup worktrees <ROOT> --yes` after the user confirmed the
  dry-run list. It removes every merged worktree under the root (even a narrower `<ROOT>` takes all merged ones of
  that repo), so re-run the dry run right before `--yes` if the overview is older than a few minutes, and use it
  only when the user confirmed the whole list. If they picked a subset, run `bdt cleanup worktree --confirm` from
  inside each picked worktree instead. Add `--keep-dbs` if the user wants to keep the databases. A worktree you just
  created from `origin/main` with no commits yet also counts as "merged", so never run it from, or on a root
  containing, the worktree you are working in unless the user wants that one gone too.
- **Orphaned test DBs**: `bdt cleanup orphaned-dbs <ROOT> --yes`. Leave out `--include-caution` unless the user
  checked the flagged DBs. A non-local `--pg-host` makes bdt ask for a typed `yes` that no flag bypasses; leave
  that prompt to the user, never work around it.
- **One specific worktree** (user names it, merged or not): from inside it, `bdt cleanup worktree --confirm`
  (add `--keep-db` to keep its DB); it refuses main/test, locked and dirty worktrees. `bdt cleanup db --confirm`
  drops only that worktree's test DB(s) and keeps the worktree.
- **Unmerged worktrees** (only the ones `bdt cleanup inspect` marks `safe`, after the user picked them):
  `bdt cleanup worktree --confirm` from inside each, or `git -C <repo> worktree remove <path>` if bdt is not
  installed, never `--force`, never `rm -rf` (that leaves dangling metadata and the test DB). Branches stay, so
  the work is recoverable. Finish with `git -C <repo> worktree prune`. For 50+ removals write the list to a file
  and loop in the background; each removal is slow because of node_modules. Re-run `bdt cleanup inspect` first if the
  overview is older than a few minutes: a session may have started since.
- **Podman**: the 60 GB the folder shows is the VM's raw disk file, which only grows. Compare it with
  `podman system df` (the real content, often under 10 GB) and say so in the overview, because `prune -a` alone
  frees only the reclaimable part and the Mac's free space barely moves. Space comes back via
  `podman machine ssh -- sudo fstrim -av` (non-destructive, offer it first); recreating the machine frees the rest
  but deletes all containers and volumes, so only with explicit agreement. Check `podman ps` first.
- **uv / npm / bun / pnpm / brew / NuGet**: their own `cache clean` / `prune` / `dotnet nuget locals all --clear`
  commands, not `rm -rf`.
- **Rust**: `target/` dirs (stale ones via `bdt cleanup stale-envs`, next to a `Cargo.toml`) are the big win; the cargo
  registry/sccache are cheap to clear. Installed toolchains are a decision row: show `rustup toolchain list` and
  never uninstall the default.
- **.NET**: stale `bin/` + `obj/` (only next to a `.csproj`/`.fsproj`/`.vbproj`) come back with `dotnet build`.
- Do not touch `~/Library/Caches` entries that were not listed; Apple and system caches are not ours.

## 4. Report

Print free space before and after (`df -h ~`), what was removed per row, and what was skipped and why. If a
removal failed, say which and leave it; do not escalate to `--force` without asking.

## Ideas worth suggesting after (only mention, do not do)

`docker`/`podman` auto-prune cron, `bdt cleanup worktree --confirm` as a habit right after a PR merges, moving
`UV_CACHE_DIR`/podman machine disk to an external drive.
