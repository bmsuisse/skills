---
name: fabricks-devops-issues-resolver
description: >
  End-to-end resolver for Fabricks.Runtime DevOps issues that have already been
  diagnosed and locally fixed by the fabricks-devops-issues skill: commits and
  pushes the fix, reruns the affected job on Databricks to verify it actually
  works, and — only after explicit confirmation — closes the ticket with a
  root-cause comment. This is a superset of fabricks-devops-issues: it pushes
  commits and kicks off real Databricks job runs, which fabricks-devops-issues
  deliberately never does. Use this skill whenever the user wants to verify a
  fix by rerunning the job, close/resolve a DevOps issue after fixing it, or
  says "rerun this job", "verify the fix", "close issue <id>", "resolve issue
  <id>". Trigger on /fabricks-devops-issues-resolver, "verify and close issue
  <id>", "rerun and resolve <table>".
---

# Fabricks DevOps Issues Resolver

Picks up where `fabricks-devops-issues`'s `diagnose <id>` leaves off (a local,
uncommitted file fix) and carries it through to a verified, closed ticket.
Read that skill first if you haven't already — this one assumes its
`list`/`diagnose` output and reuses its file-resolution logic.

This skill has real side effects `fabricks-devops-issues` doesn't: it commits
and pushes to the user's own branch, runs real Databricks jobs, and can close
real tickets. Treat every write (push, job run, ticket close) as something to
narrate plainly, not do quietly — the user should never be surprised by what
happened when they read back the conversation.

You'll need `<repo_root>` (the Fabricks.Runtime checkout) and the user's own
dev branch name (e.g. `dev_dominik`) — ask if not already clear from context.

## Step 1: commit and push the diagnosed fix

Databricks runs the job by pulling from the git **remote**, not local disk —
a fix that's only edited on disk (as `diagnose` leaves it) will not be picked
up by a rerun no matter how many times you retry it. Before verifying:

1. Show the user `git diff` for the fixed file and confirm they want it
   committed — this is git history now, a bigger step than the local edit
   `diagnose` already made.
2. Commit to their own dev branch (never `main`/a shared branch) with a
   message describing the root cause, and push it.

If the user only wants the local diagnosis (not verification), stop after
`diagnose` — this whole skill is for when they want to go further.

## Step 2: rerun the job

The project's `justfile` has `run-job TABLE: uv run drop_create_run --table
{{TABLE}}`, but for schema-drift tickets specifically, run it directly with
an explicit type:

```bash
uv run drop_create_run --type auto-schemaupdate --table <schema.table> --profile <profile> --no-mail
```

- Use `auto-schemaupdate`, not `run-schemaupdate`, as the default for any
  schema-drift ticket. `run-schemaupdate` only auto-widens compatible type
  changes and still raises `SchemaDriftException` on anything narrowing
  (e.g. `string -> int`) or otherwise incompatible; `auto-schemaupdate`
  drops/recreates as needed and has resolved both "added column" and
  "changed type" drift reliably.
- `<profile>` must match the Databricks host the job actually needs, not
  whatever the default profile happens to be — `~/.databrickscfg` has
  multiple profiles (`premium`, `standard`, etc.) for different workspace
  hosts. Get this from the run's own `run_page_url` (step 3) rather than
  assuming; a mismatched profile produces a "refresh token invalid" error
  that has nothing to do with the actual job and will send you down the
  wrong path if you don't recognize it as a profile mismatch.
- Ignore the trailing `NotImplementedError: No usable implementation
  found!` traceback every invocation prints — it's `plyer`'s desktop-notify
  facade failing on a headless box with no dbus/notify-send, unrelated
  noise. Never treat it (or the CLI exit code in general) as the
  success/failure signal; verification is step 3, not this exit code.

## Step 3: verify the rerun actually succeeded

Don't trust stdout parsing (spinner characters make it messy) or the exit
code. Use the run's own `run_page_url` to get the run ID and profile, then:

```bash
databricks jobs get-run <outer_run_id> --profile <profile>
# check .state.result_state == "SUCCESS"
```

If it's `FAILED`, the outer `state_message` is just "Workload failed, see
run output for details" — drill into the actual task for the real error:

```bash
databricks jobs get-run <outer_run_id> --profile <profile>        # -> .tasks[0].run_id
databricks jobs get-run-output <task_run_id> --profile <profile>  # -> .error has the real exception
```

If it's a genuine `AnalysisException: UNRESOLVED_COLUMN` (not a
schema-drift ticket) and the suggested alternatives look like a rename
(e.g. `previous_date` missing, `date` suggested), search git history for
when the column was actually dropped/renamed instead of guessing:

```bash
git log --all -p -S"<missing_column_name>" -- <path/to/producing_job.sql>
```

This turns a guess into a confirmed root cause (and an author to credit or
ask) — cheap to run, don't skip it in favor of speculation.

## Step 4: watch for chained drift across dependent tables

Fixing one table's drift doesn't guarantee a downstream table that reads
from it is now fixed too — if issue B's SQL selects a column from table A,
and A also has an open schema-drift ticket, B's rerun will keep failing
with the same `UNRESOLVED_COLUMN` until A's fix has actually landed (pushed
and rerun, not just diagnosed). Check an issue's SQL for references to
other gold tables before assuming it's independent; fix upstream tickets
first, then retry downstream ones.

## Step 5: close the ticket — only after explicit confirmation

Once step 3 confirms `SUCCESS`:

1. Draft the state change and a root-cause comment (what was wrong, what
   the fix was, the rerun that verified it).
2. Show both to the user and wait for explicit confirmation before writing
   anything — a verified-green rerun is good evidence, but closing/writing
   to the tracker is still a state change to a real ticket, and gets the
   same treatment as any other write in this family of skills (see
   `fabricks-devops-issues`'s `assign`).
3. Only then run `scripts/set_state.sh <id> <state>` (state name must be a
   real one for this project — see `fabricks-devops-issues`'s note on not
   guessing state names) and `scripts/add_comment.sh <id> "<text>"`. Both
   reuse the same auth as `issues.py` (`AZURE_DEVOPS_PAT`, falling back to
   an az CLI token) via `scripts/auth_token.sh` — `issues.py` itself has no
   set-state or add-comment command, hence these standalone scripts.

## Easy-fix triage refinements (extends `fabricks-devops-issues`'s `list`)

Two patterns confirmed across real triage batches:

- A bare `SchemaDriftException` ticket (added/changed columns, no other
  exception type) is a **no-code-change fix** — rerunning with
  `auto-schemaupdate` resolves it. Treat these as "easy" without routing
  them through `diagnose`'s file-read-and-edit flow at all; the fix is the
  rerun, not an edit.
- A ticket whose description is a bare `PostRunInvokeException(Py4JJavaError
  (...))` or literally `type None message None traceback None` — no real
  message text — is not diagnosable from the ticket alone. Skip it in the
  easy-fix batch without spending a file-read on it; pulling the actual
  Databricks run log first is a bigger step than this triage pass does.

## Boundaries

- Every write — commit, push, job rerun, ticket state change, ticket
  comment — gets narrated plainly as it happens. None of them happen
  silently, and closing a ticket always waits for explicit confirmation
  even after a verified-successful rerun.
- Commits go to the user's own dev branch, never `main` or a shared branch,
  and only after they've seen the diff.
- Don't surface personal details beyond what the workflow needs (a commit
  author found via `git log -S` is expected output when tracking down a
  root cause; don't dig up or repeat anything else about a person).
