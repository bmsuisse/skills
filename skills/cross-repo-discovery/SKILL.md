---
name: cross-repo-discovery
description: >
  Discover repos across the whole Azure DevOps org — not just the one you're
  sitting in — and figure out where a piece of functionality actually lives
  before assuming it doesn't exist locally. Generates ALL_REPOS.md, a map of
  every project/repo in the org, each repo's description, and whether it's
  already cloned locally (and where). Use this whenever the user asks about
  "other repos", "which repo has X", cross-repo/cross-service work, wants to
  find or clone a repo they don't have locally yet, or when you're stuck
  looking for code that isn't in the current repo and it might live elsewhere
  in the org. Trigger on things like "is there already a repo for this",
  "check across our other repos", "what repos do we have", "where's the
  shared X library", or "I don't think this exists yet, can you check devops".
compatibility: Requires az CLI with the devops extension, `az login` completed, and uv (or python) to run the script.
---

# Cross-repo discovery

Most repos only see their own code. When a question spans the org — "does
another repo already do this", "where should this shared logic live", "is
there a repo for X that I haven't cloned yet" — the fix isn't to guess from
one repo's contents, it's to look at the org's repo map first.

## Quick start

1. Check whether `ALL_REPOS.md` already exists in the local work dir (see
   below for how that path is resolved). If it exists, read it before doing
   anything else — it's usually cheaper and more current than re-running the
   script.
2. If it's missing, stale, or the user explicitly wants a refresh, run:
   ```bash
   uv run scripts/list_azdo_repos.py --org <org>
   ```
   This requires interactive input to pick which projects/repos to include
   (see below) — plan to hand control back to the user for that, or pass
   `--all` to include everything without prompting.

## What the script does

`scripts/list_azdo_repos.py`:
- Lists every project and repo in an Azure DevOps org via `az devops`.
- Reads each repo's description (stored in a `Repos:` section of the
  project's DevOps description field — one `repo-name: description` line per
  repo) and lets you add a description for repos that don't have one yet,
  optionally pushing it back to DevOps.
- Scans a local "work dir" for existing git clones and matches them to org
  repos by normalized remote origin URL, so you know at a glance which repos
  are already checked out and where.
- Writes/updates `ALL_REPOS.md` at the root of the work dir: a table of
  `Project | Repo | Remote URL | Local Clone(s) | Description`.

It's read-only against your local filesystem (it only walks directories
looking for `.git`) and only writes to DevOps if you explicitly opt in to
setting a description.

## Requirements

- `az` CLI on PATH, with the `azure-devops` extension, and `az login` already
  run for the target org.
- `uv` (the script is a self-contained `uv run --script`) or plain `python3`.

## Configuration

The org is **required** — the script does not guess or hardcode one:

| How | Example |
|---|---|
| `--org` flag | `uv run scripts/list_azdo_repos.py --org contoso` |
| `AZDO_ORG` or `BMS_ORG` env var | set in shell, or in a local `.env` file next to where you run it |

If neither is set, the script exits with an error rather than prompting —
pass `--org` or set the env var.

The local clone root ("work dir") is resolved from `AZDO_WORK_DIR` or
`BMS_WORK_DIR` (either name works), falling back to `C:/Projects` on Windows
or `~/projects` elsewhere. This is where the script looks for existing clones
and where it writes `ALL_REPOS.md`.

## Usage

```bash
# Interactive: pick which projects/repos to include
uv run scripts/list_azdo_repos.py --org <org>

# Non-interactive: include every project and repo
uv run scripts/list_azdo_repos.py --org <org> --all

# Re-sync repo descriptions after hand-editing ALL_REPOS.md
uv run scripts/list_azdo_repos.py --org <org> --sync-descriptions
```

`--sync-descriptions` re-reads `ALL_REPOS.md`, lets you edit each repo's
description interactively, and pushes changes back to the DevOps project
description — use it after manually cleaning up descriptions in the
generated file rather than re-answering every prompt from scratch.

## Reading ALL_REPOS.md as an LLM

The generated file looks like:

```markdown
# Azure DevOps Repos

Org: contoso
Local work dir: C:/Projects

| Project | Repo | Remote URL | Local Clone(s) | Description |
|---|---|---|---|---|
| Platform | auth-service | https://dev.azure.com/contoso/Platform/_git/auth-service | C:/Projects/auth-service | Shared auth/session library |
| Platform | billing-api | https://dev.azure.com/contoso/Platform/_git/billing-api | - | Billing and invoicing API |
```

When you're asked about code that might live in another repo:
1. Read `ALL_REPOS.md` first, before concluding something "doesn't exist" —
   grep the Description and Repo columns for relevant keywords.
2. If a matching repo has a **Local Clone** path, read/search there directly.
3. If it doesn't have a local clone, tell the user which repo it is and offer
   to clone it (`git clone <Remote URL>`) rather than reimplementing
   something that already exists elsewhere in the org.
4. If nothing in the table looks relevant, say so explicitly rather than
   silently assuming the file's absence means no such repo exists — the file
   may simply be stale or the user may have chosen not to include every
   project when it was generated.
