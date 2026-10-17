---
name: history-lessons
plugin: coding
description: >
  Mine a mature repo's git history (reverts, commits that state a root cause,
  refactors, repeatedly-fixed files, optionally PR review comments) to learn
  what the team corrected over time, then distil that into short,
  evidence-backed rules for AGENTS.md / CLAUDE.md. Use when the user wants to
  teach agents "what good code means here", bootstrap or refresh AGENTS.md from
  an existing repo, learn conventions from commit history, or asks "what do we
  keep getting wrong", "what did we learn", "derive guidelines from our
  commits" — even if they never say "history".
---

# History Lessons

Current code shows what the repo *is*. History shows what the team *corrected*
— the only place "we tried X, it was wrong, now we do Y" is recorded. This skill
turns those corrections into AGENTS.md rules.

The signal is the **delta**, not old-vs-new. Old code nobody touched again is
fine. A rule needs a correction behind it.

Works best on repos with months of history and revert/fix discipline. A repo
younger than ~a month, or one written in one agent sweep, has few corrections:
say so and return fewer rules (or none) instead of padding.

## Steps

1. **Mine.** Read-only (`origin/HEAD`, no checkout or pull; `git fetch` first if
   stale). The script sits next to this SKILL.md:

   ```bash
   python3 scripts/mine.py <repo> [--since YYYY-MM-DD] [--top 25]
   ```

   Seconds, git only. The header prints commit count, date range and which
   agent docs exist. `--since`: only for repos with more than ~1500 commits; use
   about 9 months before the newest commit (a date older than the first commit
   does nothing). Add `--prs 40` only if the team really reviews in Azure DevOps
   PR threads: it takes minutes and on the BMS repos returned only the PR
   author's own status logs, so default is off. Foreign repos may need the
   sandbox disabled for `git -C`/`az`.

   Sections, best first: **Reverts** (with the body's first line as `why:`),
   **Commits that state a cause or rule**, **Refactors** (spread over time,
   lint sweeps skipped), **Files fixed most often** (churn only: a pointer to
   "ask first" areas, never a rule by itself). Commits are deduped by subject
   (cherry-picks count once).

2. **Dig.** For each candidate read the full message:
   `git show -s --format=%B <sha>` (never plain `git show`: merge or huge diffs).
   A merge-revert (`Revert "Merge pull request …"`) has no reason in the
   subject; look at the reverted PR's commits. The digest misses fixes without a
   `fix:` prefix, so also run
   `git log origin/HEAD --format='%h %as %s' -i --grep='<topic>'` for any theme
   you suspect. Drop CI/status logs and build ids.

3. **Cluster into themes** (auth, infra, abstraction, typing, UI taste, tests…).
   Keep a rule only if it has **≥2 independent corrections** — different days
   or PRs; commits of one PR, cherry-picks, and several reverts inside one
   feature area count once — or one revert that cites an explicit rule or
   constraint. Before keeping a rule, `git grep` that the feature or file still
   exists on `origin/HEAD`: rules about retired code are noise.

4. **Draft rules**: imperative, one line, each with evidence SHAs as printed by
   the digest. Cover do, don't, and "ask first" (areas reverted for lacking
   approval, or feature removals that were reverted on feedback). "None found"
   is a valid answer for any kind.

5. **Check against the repo's agent docs, read from `origin/HEAD`** (not the
   possibly dirty working tree): `git show origin/HEAD:AGENTS.md`. Follow its
   pointers (an AGENTS.md that is only a pointer list means the rules live in
   e.g. `docs/CONSTITUTION.md`). No AGENTS.md: use CLAUDE.md or a docs/*STANDARDS
   file from the header line. None at all: this is a bootstrap, nothing to
   dedupe, and ask the user where the section should go. Large files overflow
   the tool output, so save to a file and grep. Skip rules already stated (that
   is a confirmation: mention it, e.g. "auth ban matches 5 reverts"); flag docs
   the history contradicts.

6. **Show the draft in chat and wait** (interactive runs; a delegated run stops
   at step 5 and writes the draft to the file it was told to). The rules must be
   visible in the message, not only in a file. Only after approval write them
   into the agent doc in a worktree off the integration branch, following the
   repo's own commit flow; don't push unless asked. Keep the section ≲30 lines.

## Output shape

```markdown
## Lessons from history
- <Imperative rule, one line, with the reason in a clause>. (<sha>, <sha>)
- <Ask-first rule: "Ask before changing X"; reverted N times on feedback>. (<sha>, …)
```

## Pitfalls

- Reverts of *features* (logo, sidebar) are product taste, not code rules; keep
  only if they recur and phrase as "ask the user first".
- Churn is not correction: a file touched 60x is big or central, not wrong.
- A swarm of agent commits on one day is one session fixing its own output, not
  a team lesson.
- Don't paste commit lists into AGENTS.md. Rules + SHAs only.
- Tested on OneSales, OneHub, OneDocs, OneBrain: rules came mostly from
  reverts and from commit bodies stating a root cause.
