# Unrelated bugs found along the way

A bug tied to what you're actually building gets fixed inline per step 3 of
the main workflow. A bug that's unrelated to the current task should NOT be
fixed inline — file it and hand it off instead:

1. Search for an existing issue first: `bdt issue search <keywords>`. Defaults
   to open issues/work items from the last 30 days; pass no keywords to just
   list them, `--state closed`/`--state all` to widen the state filter, and
   `--since-days 0` to drop the date filter.
2. If none exists, create one: `bdt issue create --title "..."`.
3. If an issue already exists and someone (another session or person) is
   already on it — e.g. it already has a "working on it" comment — leave it
   alone; don't spawn a subagent for it.
4. Otherwise, kick off a subagent to resolve it. Instruct it to first
   research the bug itself and confirm it's genuinely unrelated to the
   current task before doing anything else — only once it's really sure
   should it set up its own separate worktree to work in (never the current
   task's worktree). Its next action, before any fix, must be commenting on
   the issue with its session id and that it's working on it:
   `bdt issue comment add <number> --body "..."`.
5. The subagent closes the issue once the fix is resolved:
   `bdt issue update <number> --state Closed` (works on both backends).

## bdt issue tooling reference

`bdt issue create|search|update|delete` and `bdt issue comment
add|update|delete`, auto-detecting Azure DevOps vs. GitHub from the git
remote. `create` prints just the issue link; `search` prints `#<number>
[<state>] <title>` plus the link per match. `update --state Closed`/`Done`/
`Removed`/`Open` work on both backends; other state names (e.g. Active,
Resolved) only apply where that exact name exists for the work item's
type, else the state is left unchanged and noted in a comment. `--board`
(create/search, scopes to that Azure Boards team's Area Path — falls back
to `[tool.bdt.ado].board` in pyproject.toml) and `--tag` are Azure
DevOps-only; `--label` is GitHub-only.
