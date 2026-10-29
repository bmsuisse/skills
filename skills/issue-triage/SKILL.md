---
name: issue-triage
plugin: dev-workflow
description: Triage business users' Azure DevOps work items: research, then mark ready for an agent or ask business/technical questions (tags needs-business, needs-techie).
---

# Issue triage

Business users file work items with vague wording ("faster", "like before", "the usual customers"). Triage turns each
one into either **ready for an agent** or **a short list of questions to the right people**, so nobody starts
implementing a guess. Needs `bdt` 0.47+ (`uv tool upgrade bmsdna-devtools`). Triage never changes the state or the
assignee, and never edits code: it researches, comments and tags.

## 1. Pick the items

```bash
bdt issue search --business-user                    # open items created by business users
bdt issue search --business-user --tag needs-business   # waiting for a business answer (same for needs-techie)
```

`--business-user` means a Stakeholder license, or no commit in the last 1000 commits of the repo you run it in (so run it
in the repo the work items belong to). Take an item if it has neither tag and no earlier triage comment, or if it has a
tag and its newest comment is a reply (not a triage comment): a reply means re-triage (step 5).

## 2. Research first

`bdt issue show N --json` (description, comments, creator). Then find out what the request is about before judging it:
search the code (`codegraph explore` if the repo has `.codegraph/`, else grep), look for the screen / endpoint / table
it names, similar work items (`bdt issue search <keywords> --state all`), and other repos (`cross-repo-discovery`).
Upload the findings to the work item (step 4), even when you end up asking questions: the next reader should not
repeat your research. Questions the code or the history can answer are not questions; answer them yourself.

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

One comment per triage, so the work item's author gets one notification. Write the business part in plain language
for non-developers: no jargon, no code names. Make questions easy to answer: closed or multiple choice, with your
suggested default ("Should the list show only open orders? Proposed: yes").

Not ready (omit an empty section):

```markdown
**Triage**

**What I found**
- <research findings, with file / screen / work item references>

**Questions for the business**
1. ...

**Questions for the developers**
1. ...
```

Ready: start the comment with `@Agent` (that is what `bdt issue search --for-me` picks up), then the findings, the
files / places to change and the acceptance criteria you derived.

```bash
bdt issue comment add N --message "$(cat comment.md)"
```

Tags, set by what is open: `needs-business` if there is any business question, `needs-techie` if there is any
technical one, both if both, neither if ready. On Azure DevOps `--tag` **replaces the whole tag list**, so pass the
existing tags too (from `issue show`), or use `--remove-tag` to drop a single one:

```bash
bdt issue update N --tag <existing> --tag needs-business --tag needs-techie
bdt issue update N --remove-tag needs-business
```

## 5. Re-triage on a reply

Read the new comments, remove the tag whose questions are now all answered (leave the other), and decide again (step 3).
Answers that raise new vagueness get a new, short triage comment with only the open questions. When both tags are
gone and the item holds up, mark it ready with the `@Agent` comment. To wait for an answer instead of coming back
later: `bdt issue watch N --since-comment ID --skip-own`.

## Notes

- If `bdt issue show` says the license is unknown, the PAT lacks the *Member Entitlement Management (read)* scope; the
  commit check still decides, so the result can be wrong for developers who commit elsewhere. Say so in your summary.
- Don't triage an item an agent has already taken (newest comment `Taken by ...`).
