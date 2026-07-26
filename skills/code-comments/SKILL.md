---
name: code-comments
plugin: coding
description: >
  Write and review code comments so they earn their place instead of adding
  noise. Use this whenever writing new code (to decide whether a comment is
  needed and how to phrase it), whenever reviewing a diff or file for comment
  quality, and whenever the user says things like "review these comments",
  "are these comments any good", "clean up the comments in this file", "should
  I comment this", "add docstrings", "this comment is redundant/noisy/rude",
  or "audit comments before this PR". Also trigger proactively before
  finishing any coding task that added or touched comments -- don't wait to be
  asked. Covers Python, JavaScript, TypeScript, and React (JSX/TSX).
---

# Code Comments

Most comments are unnecessary. The valuable ones survive because they carry
information the code itself cannot: **why**, not **what**. This skill governs
both directions: writing comments as you code, and reviewing/cleaning up
comments that already exist.

**Default to fewer comments, not more.** When torn between adding a comment
and leaving the code to speak for itself, leave it alone — a missing comment
costs a reader a few seconds of reading the code; an unnecessary one costs
every future reader that same tax, forever, and clutters the file's signal.
Comment count is not a proxy for code quality or thoroughness. A file with
zero comments and clear names is a better outcome than the same file with
five comments restating what the names already say — never add a comment
just to look complete or "well-documented."

## The one test that matters

Before writing or keeping a comment, ask: **if I deleted this comment, would
a competent reader of this codebase be missing something they couldn't get
from the code, a better name, or a type?**

- If the answer is no → delete it, or better, rename/restructure the code so
  it wasn't needed in the first place.
- If the answer is yes → keep it, and make sure it explains the *why*, not
  the *what*.

This single question replaces most style-guide checklists. Everything below
is detail in service of that test.

## Two kinds of comment, and only two

**Documentation comments** (docstrings, JSDoc, public API docs) are for
consumers who won't read the implementation — library users, other teams,
your own future self skimming an API. They document the contract: inputs,
outputs, side effects, invariants. Keep these close to the code they describe
so they can't drift, and hold them to whatever the language's doc-comment
convention is (docstrings in Python, JSDoc in JS/TS).

**Clarification comments** are for maintainers reading the implementation.
These should be rare. A clarification comment is usually a signal that the
code itself is more complex than it needs to be — the fix is often to
simplify or rename, not to annotate. The clarification comments worth keeping
explain something invisible in the code:

- A non-obvious workaround: *why* this weird-looking line exists, tied to a
  specific constraint (a browser bug, a race condition, a library quirk).
- A rejected alternative: you tried the "obvious" fix, it was wrong, and
  whoever comes next needs to know that before they "helpfully" redo it.
- A business rule or external constraint that isn't derivable from reading
  the function (a legal requirement, an off-by-one that matches a vendor's
  API, a magic number from a spec).

If a comment doesn't fit one of those, it's very likely restating the code
in English and should go.

## What to strip on sight

| Pattern | Example | Why it goes |
|---|---|---|
| Restates the code | `# increment i by 1` above `i += 1` | Zero information beyond the code |
| Commented-out code | `// oldImplementation()` | Git history is the record for this, not the file |
| Change-log / narration comments | `// fixed bug here 2019` | Belongs in the commit message, rots in place |
| Apology or self-deprecation | `// sorry this is ugly` | Fix it or leave a real reason; an apology helps no one |
| Venting / mean-spirited | `// workaround for Dave being careless` | Unprofessional, ages badly, says nothing technical |
| Vague TODO with no owner or context | `// TODO: fix this later` | A TODO is only useful if it says *what* and *why*; otherwise it's permanent driftwood |
| Comment as joke/rhyme in place of a fix | a clever poem explaining a regex | Entertaining once, then it's the thing blocking someone from refactoring it |
| Type info already expressed by the type system | `// x is a string` above `x: str` | The signature already says this |

## What earns a comment

```python
# Bad -- restates the code, tells you nothing new
# set age to 32
age = 32

# Good -- code doesn't need a comment, so it doesn't have one
age = 32
```

```python
# Bad -- no comment, but the choice looks like a mistake to the next reader
def get_user(id):
    return db.query(f"SELECT * FROM users WHERE id = {id}")

# Good -- explains a constraint invisible in the code
def get_user(id):
    # Raw query, not the ORM: this table is sharded and the ORM's query
    # planner doesn't route by shard key, causing a full scan across shards.
    return db.query(f"SELECT * FROM users WHERE id = {id}")
```

```javascript
// Bad -- funny but doesn't replace the fix that's actually needed
/*
 * Replaces with spaces the braces in cases where braces in places cause stasis.
 */
str = str.replace(/[{}]/g, " ");

// Good -- either just name it well...
const sanitized = removeCurlyBraces(input);

// ...or, if the "obvious" fix was already tried and rejected, say so:
function addSetEntry(set, value) {
  // Not `return set.add(value)` -- Set#add isn't chainable in IE11.
  set.add(value);
  return set;
}
```

```typescript
/**
 * Formats an amount as localized currency for display.
 *
 * @param cents - amount in the smallest currency unit (avoids float rounding)
 */
export function formatCurrency(cents: number, locale: string): string {
  ...
}
```

More paired good-vs-bad examples per language (Python, JS/TS, React) are in
`references/examples.md` — read it when the cases above aren't enough, or
when you need extra reference material for writing eval test cases.

## Writing mode: while you code

When you're about to add a comment, run it through the test above first. In
practice this means:

1. Try to make the comment unnecessary — rename the variable/function, or
   extract a clearly-named helper — before reaching for a comment.
2. If a comment is still warranted, write the *why*: the constraint, the
   rejected alternative, the non-obvious tradeoff. Not the *what*.
3. For anything public (an exported function, an API endpoint, a shared
   library entry point), add a real documentation comment in the language's
   convention (docstring / JSDoc) describing the contract, not the internals.
4. Never vent, apologize, or joke in place of fixing something. If the code
   is bad, either fix it now or leave a comment naming the actual constraint
   that's stopping you (deadline, unresolved dependency, known limitation) —
   not a shrug.

## Review mode: auditing existing comments

When asked to review or clean up comments in a file, diff, or PR:

1. **Locate every comment with context.** For small files just read them
   directly. For larger files or a full audit, use the bundled extractor so
   you see each comment next to the code it sits in, without re-reading the
   whole file:

   ```bash
   python3 <skill-path>/scripts/extract_comments.py <file> [<file> ...]
   ```

   Supports Python, JS, TS, JSX, and TSX. Output is JSON: each entry has
   `file`, `line`, `kind` (`line` / `block` / `docstring`), `text`, and
   `context` (the surrounding code). It's a heuristic scanner, not a full
   parser — good enough to triage comments in a large file, not a substitute
   for reading the actual diff on anything it flags as borderline.

2. **Judge each comment against the one test.** For each one, decide: keep as
   is, keep but rewrite (usually to explain *why* instead of *what*), or
   delete (and if deleting reveals the code itself is confusing, suggest the
   rename/extraction that would make the comment unnecessary).

3. **Report findings**, one line per comment that needs action:

   ```
   ## Comment review

   ### Delete
   - file.py:42 — restates the assignment above it, no new information

   ### Rewrite
   - api.ts:110 — explains *what* the regex does; rewrite to explain *why*
     this pattern and not a simpler one (ties to the vendor's date format)

   ### Add
   - utils.py:8 — exported function with a non-obvious contract (rounds
     toward the caller's timezone); needs a docstring

   ### Keep as is
   - db.py:77 — documents a rejected "obvious" fix, exactly the kind of
     comment worth keeping
   ```

   If a file's comments are already clean, say so — don't manufacture
   findings to look thorough.

## The line on tone

Comments are read by colleagues, code reviewers, whoever's on call at 3am,
and your own future self. Frustration, sarcasm, or blame aimed at a person
doesn't belong in source that ships — it reads as unprofessional long after
the frustration has faded and the person named has moved on. If the
underlying issue is real (a bad interface, a rushed deadline, a workaround
you're not proud of), say what the issue actually is instead of venting about
it. That version is still useful in six months; the vent isn't.
