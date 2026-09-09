# Unrelated bugs found along the way

A bug tied to what you're actually building gets fixed inline per step 3 of
the main workflow. A bug that's unrelated to the current task should NOT be
fixed inline — file it and hand it off instead:

1. Search for an existing issue first (bdt has no issue search/list — use
   `gh issue list --search "<keywords>"` for GitHub repos, or `az boards
   query`/the Boards UI for Azure DevOps repos).
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
5. The subagent closes the issue once the fix is resolved: `bdt issue update
   <number> --state Closed` (Azure DevOps), or `gh issue close <number>`
   (GitHub — `--state` on `bdt issue update` is Azure DevOps-only and is
   silently ignored on GitHub repos).

## bdt issue tooling reference

`bdt issue create|update|delete` and `bdt issue comment add|update|delete`,
auto-detecting Azure DevOps vs. GitHub from the git remote. `create` prints
just the issue link. There's no `list`/`search` subcommand — fall back to
`gh issue list` or `az boards query` for that. `--board`, `--tag`, and
`--state` are Azure DevOps-only; `--label` is GitHub-only.
