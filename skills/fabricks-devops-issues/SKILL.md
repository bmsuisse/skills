---
name: fabricks-devops-issues
description: >
  Orchestrates Azure DevOps "Issue" work-item workflows in the Fabricks.Runtime repo —
  listing open issues so the user can pick one, surfacing which ones look like easy/
  low-hanging-fruit fixes, auto-assigning issues by git blame, reporting on open issues,
  and diagnosing (and locally fixing) a job-run error from an issue. Use this skill
  whenever the user asks to list, triage, assign, or report on DevOps issues in
  Fabricks.Runtime, or asks "what's wrong with issue <id>" / "diagnose issue <id>" /
  "who should this ticket go to" / "which issues are easy to fix" / "what are the
  low-hanging fruit". Trigger on /fabricks-devops-issues, "list the devops issues",
  "assign the devops issues", "report on open issues", "diagnose issue <id>", "which
  issues can I fix quickly".
---

# Fabricks DevOps Issues

Thin orchestration layer over `issues.py`, a PEP 723 script at the root of
Fabricks.Runtime. It's already implemented and tested — this skill does not
write or modify any Python in that repo. It calls `issues.py` through the
bundled `scripts/` in this skill directory (not through Fabricks.Runtime's
own `justfile` — that's a convenience wrapper for humans and may not be
present or up to date wherever this skill runs; the scripts here call
`uv run issues.py` directly so the skill works regardless).

Auth is handled inside `issues.py` (Azure CLI access token, falling back to
the `AZURE_DEVOPS_PAT` env var) — never ask the user for a token.

You'll need the path to the Fabricks.Runtime checkout (`<repo_root>` below)
— ask the user if it's not already clear from context.

Dispatch on the first word of the request: `list`, `assign`, `report`, or
`diagnose <id>`.

## list

1. Run `scripts/list.sh <repo_root> [--state STATE] [--assigned-to PERSON]`
   to get the raw ID/state/assignee/title table, and show it to the user so
   they can pick which one to dig into with `diagnose <id>`.
2. If the user instead asks for the easy ones / low-hanging fruit: take a
   reasonable-sized batch of open issues (unassigned or otherwise — cap it,
   maybe 5-10, rather than diagnosing every open issue, since each one costs
   a `get` call plus a file read), run steps 1-3 of `diagnose` on each (get
   the issue, resolve the job file, read it), and judge from the error and
   the file how contained the fix looks — a single renamed/missing column,
   a typo, an off-by-one config value read as easy; anything spanning
   multiple files, an unclear stack trace, or a schema/architecture change
   is not. Present a short ranked list (issue, one-line reason it looks
   easy or not) and let the user pick — don't apply any fix during this
   pass, that only happens once they choose one and you move into the
   `diagnose` flow for it.

## assign

Auto-assignment resolves each issue's title (format `STEP.TOPIC_ITEM`) to a
repo file by matching `job.step`/`job.topic`/`job.item` fields inside
`_config.*.yml` files — folder layout doesn't reliably mirror step/topic
names, so this is a field match, not a path guess. It then assigns the issue
to the last git committer of that file (or a sibling `{item}.sql` if one
exists).

1. Run `scripts/auto_assign.sh <repo_root> --dry-run` and show the user the
   resolved issue → assignee mapping. With no `--id`, this only considers
   issues that are currently unassigned — it won't reassign something
   already owned by someone.
2. Only run `scripts/auto_assign.sh <repo_root>` for real (no `--dry-run`)
   after the user explicitly confirms. This writes to Azure DevOps and must
   never happen silently — a wrong auto-assignment is annoying to undo by
   hand.

## report

1. Run `scripts/report.sh <repo_root>`.
2. Summarize back in prose: counts by state/assignee, and anything that
   stands out (one assignee carrying a disproportionate share, issues open
   far longer than the rest). Don't just paste the raw report — the point
   is to surface what a human would otherwise have to notice themselves.

## diagnose \<id\>

1. Run `uv run issues.py get <id>` (from `<repo_root>`) to pull the title,
   state, and the job-run error captured in the description.
2. Resolve the job's file with `scripts/resolve_job_file.py <repo_root>
   <title>` — it prints the path of the sibling `{item}.sql` if one exists,
   otherwise the `_config.*.yml` itself. This exists as its own script
   because `issues.py`'s CLI only exposes this resolution as an internal
   part of `auto-assign`, not standalone — reimplementing the field-match
   by hand each time (rather than using this script) risks getting it wrong
   on the path-doesn't-mirror-step/topic cases.
3. Read that file's content and work out the likely root cause.
4. Apply the fix directly to the file — the point is to leave the dev a
   ready-to-review local change, not a diagnosis they have to retype
   themselves. Then tell them plainly what you changed and why, and point
   them at `git diff` to review it before deciding to commit.

Never run `git commit`, `git push`, or open a PR for this subcommand — the
edit stays local and uncommitted. The dev reviews and decides whether to
commit; committing/pushing on their behalf without review would turn a
guess (the root cause might be wrong) into a change they never looked at.
If you're not confident in the fix, say so and describe what you'd change
instead of guessing at a patch.

## Boundaries

- No changes to `issues.py` or its tests in Fabricks.Runtime — that's
  already implemented and tested elsewhere. The scripts bundled here only
  call it or replicate its read-only resolution logic.
- `assign` is the only subcommand that writes to Azure DevOps, and only
  after explicit confirmation. `diagnose` may edit a local file (see
  above) but never touches git state or DevOps. `list` and `report` are
  read-only.
- The easy-fix triage under `list` only reads issues and files to judge and
  rank them — it never edits anything. It's a batch, so keep it bounded
  (don't quietly diagnose the entire backlog); say how many you looked at.
- Don't surface personal details beyond what the workflow needs (an
  assignee name resolved by git blame is expected output; don't dig up or
  repeat anything else about a person from commit history or the ticket).
