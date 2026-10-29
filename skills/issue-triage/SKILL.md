---
name: issue-triage
plugin: dev-workflow
description: Triage business users' Azure DevOps work items: research, then mark ready for an agent or ask business/technical questions (tags needs-business, needs-techie).
---

# Issue triage

Business users file work items with vague wording ("faster", "like before", "the usual customers"). Triage turns each
one into either **ready for an agent** or **a short list of questions to the right people**, so nobody starts
implementing a guess. Triage never changes the state or the assignee, and never edits code: it researches, comments
and tags. `--business-user` needs `bdt` 0.47+ (`uv tool upgrade bmsdna-devtools`).

**Business users usually can't open pull requests** (and don't read code), so the work item is the only place where
information is exchanged with them: findings, questions, answers, status and the later result all go into comments on
it. Never answer with "see the PR" or a link to code; put what matters in the comment itself, in their words, with
screenshots or a short description of what they will see. Developers can follow along in the PR; the business user
reads the work item.

## 1. Pick the items

```bash
bdt issue search --business-user --since-days 0 --limit 30        # open items created by business users
bdt issue search --business-user --since-days 0 --tag needs-business   # waiting for a business answer (same for needs-techie)
```

The default `--since-days 30` / `--limit 10` would hide older items behind recently touched, already triaged ones. The
list shows no tags or comments, so look at each candidate with `bdt issue show N --json`.

`--business-user` means a Stakeholder license, or no commit in the last 1000 commits of the repo you run it in.
Run it in a full clone of the repo the work items belong to: in another team's repo every developer looks like a
business user, and without git history (shallow clone, no repo) it returns nothing, which is not "nothing to triage".

Take an item if it has no triage comment yet, or if its newest comment is a **reply** (step 5), tagged or not: a business
user may answer a ready item with "also include X". A reply is any newest comment that is neither a triage comment
(first line `Triage`) nor `Taken by ...`. Skip an item whose newest comment is `Taken by ...`: an agent is already
working on it.

## 2. Research first

`bdt issue show N --json` (description, comments, creator). Then find out what the request is about before judging it:
search the code (`codegraph explore` if the repo has `.codegraph/`, else grep), look for the screen / endpoint / table
it names, similar work items (`bdt issue search [keywords] --state all --since-days 0`, one or two distinctive words at a time: keywords are ANDed and match only title and description), and other repos (`cross-repo-discovery`, if available).
Upload the findings to the work item (step 4), even when you end up asking questions: the next reader should not
repeat your research. Questions the code or the history can answer are not questions; answer them yourself. If you
can't find what the item names (screen, report, field), say what you searched in "What I found" and ask the business for
its exact name or location; don't invent a technical question to fill the gap.

## 3. Decide

The item is **ready** only if all of these hold, otherwise it gets questions:

- No vague term is left. Check for: comparatives without a measure ("faster", "better", "easier"), quantities without a
  number ("some", "many", "a few"), "like before / as usual / as in X" without a reference, "etc." and "and so on",
  unnamed things (which screen, customer, report, field, role?), unclear who or when, missing expected result.
- You can name where the change goes (files, tables, screens) and what "done" looks like.
- Nothing is blocked on a decision that nobody has made.

Every question is **business** or **technical**:

- **Business**: what the user wants, rules, numbers, who may do it, priorities, and everything about **UI/UX**
  (layout, wording, where a button lives, what the screen should show). Even if a developer could guess.
- **Technical**: how it can be built, which of several feasible approaches, constraints and risks in the code, data
  or systems. Ask only what the research could not settle.

## 4. Write one comment, set the tags

One comment per triage, so the work item's author gets one notification. Write it in the language the work item is
written in. The business part is for non-developers: no jargon, no code names. Make questions easy to answer: closed
or multiple choice, with your suggested default ("Should the list show only open orders? Proposed: yes").

Both variants start with the line `**Triage**` (step 1 recognises earlier triage by it; `bdt` posts the text as
Markdown source, so check once how your org's work item renders it). Don't write angle brackets (`/orders/<id>`, `List<T>`)
in a comment: `bdt issue show` strips them as HTML tags. Write `{id}`. Not ready (omit an empty section):

```markdown
**Triage**

**What I found**
- [research findings, with file / screen / work item references]

**Questions for the business**
1. ...

**Questions for the developers**
1. ...
```

Ready: put `@Agent` on the second line (that is what `bdt issue search --for-me` picks up; plain text, no Azure
mention syntax):

```markdown
**Triage**
@Agent ready for implementation

**What I found**
- [findings with references]

**Where to change**
- [files / screens / tables]

**Acceptance criteria**
1. [observable, testable results, from the work item's own words]
```

Tags, set by what is open: `needs-business` if there is any business question, `needs-techie` if there is any
technical one, both if both, neither if ready (a ready item needs no update, except removing a `needs-*` tag that is
still on it). On Azure DevOps `--tag` **replaces the whole tag list**, so pass every existing tag as its own `--tag`
(`issue show --json` lists them in `tags`), or use `--remove-tag` to drop a single one:

```bash
bdt issue update N --tag <existing> --tag needs-business --tag needs-techie
bdt issue update N --remove-tag needs-business
```

Tags first, then the comment: if the tag update fails after the comment was posted, step 1 would never pick the item
up again. Write the comment to a temp file outside the repo (so a later `git add` can't pick it up) and delete it after.

```bash
bdt issue comment add N --message "$(cat "$TMPDIR/comment.md")"
```

## 5. Re-triage on a reply

Read the new comments, remove the tag whose questions are now all answered (leave the other), and decide again (step 3).
Answers that raise new vagueness get a new, short triage comment with only the open questions. When both tags are
gone and the item holds up, mark it ready with a new `@Agent` comment: `--for-me` only looks at the newest comment, so a
reply after an earlier ready comment hides the item from agents until `@Agent` is posted again.

Business answers take hours or days, so normally leave the item tagged and come back later. To block instead:
`bdt issue watch N --since-comment ID --skip-own --timeout 0` (the default 900 s ends with exit 4, meaning "no reply
yet", not an error; `--skip-own` is reliable only when run inside an agent session).

## After triage

When an agent implements a ready item, the result goes back to the work item too (what changed, screenshots), written
for the business user (`dev-workflow` step 11). A PR link alone is not an answer for them.

## Notes

- `bdt issue show` prints `Created by: X (business user: license unknown, ...)` when the license lookup failed (token
  without the *Member Entitlement Management (read)* scope, creator not in the org, outage). The commit check still
  decides, so the verdict can be wrong for developers who commit elsewhere. Say so in your summary.
