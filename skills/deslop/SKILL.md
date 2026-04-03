---
name: deslop
plugin: coding
description: >
  Remove AI slop from code and pull requests. Use this skill whenever the user
  wants to clean up AI-generated code, review a diff for unnecessary noise,
  audit a file or PR for style inconsistencies, over-abstraction, defensive
  checks that don't belong, redundant comments, or anything that "doesn't feel
  like it belongs here". Also use it proactively after any AI-assisted coding
  session to apply the Research → Plan → Execute → Review → Revise loop and
  ensure the output is clean, reviewable, and consistent with the existing
  codebase. Trigger on: "remove slop", "clean up AI code", "deslop", "review
  diff", "does this look AI-written", "polish this PR", "make this feel more
  human", "clean up before commit".
---

# Deslop

AI-generated code often _works_ but doesn't _belong_. It is technically
correct but inconsistent — stuffed with comments nobody would write, defensive
checks that don't match the codebase's trust model, abstractions added "just
in case", and style that clashes with the surrounding file.

This skill helps you either **reactively clean up** existing AI-written code,
or **proactively structure your AI workflow** so slop never reaches the PR in
the first place.

---

## What AI slop looks like

Before fixing anything, recognise the patterns:

| Category                  | Examples                                                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Redundant comments**    | `# increment counter by 1`, `// returns the user`                                                                               |
| **Over-defensive code**   | `if value is not None and value != "" and value != []` where `if value` suffices; unnecessary `try/except` wrapping happy paths |
| **Type escapes**          | Spurious casts, `as any`, `!` non-null assertions added "just to be safe"                                                       |
| **Inconsistent style**    | Naming conventions, import ordering, or patterns that differ from the surrounding file                                          |
| **Premature abstraction** | Hooks, interfaces, base classes, or configuration keys that serve no current requirement                                        |
| **Vibe extras**           | Logging statements, TODO comments, or fallback branches that weren't asked for                                                  |

---

## Reactive cleanup — the subtractive review

Use this when you have a diff, file, or snippet to clean up right now.

Ask yourself one question: **"Would someone who has been in this codebase for
six months write this?"**

### Checklist

Work through the diff/file systematically:

- [ ] **Comments**: Remove any comment a competent maintainer wouldn't need.
      Keep comments that explain _why_, delete ones that restate _what_.
- [ ] **Defensive checks**: Remove guards that don't match the existing trust
      model. If the rest of the codebase already validates inputs at the
      boundary, don't re-validate deep inside a helper.
- [ ] **Type escapes**: Remove `as any`, `!`, unnecessary casts, or `# type: ignore`
      unless there is a documented reason. Fix the root cause instead.
- [ ] **Naming**: Rename anything that clashes with the file's existing
      conventions (casing, prefixes, abbreviations).
- [ ] **Abstractions**: Delete layers of indirection that exist "just in case".
      YAGNI — You Aren't Gonna Need It.
- [ ] **Style**: Re-align imports, spacing, and formatting to match the
      surrounding file. Run the project's linter/formatter after changes.
- [ ] **Extras**: Remove stray `print`, `console.log`, TODO comments, and
      boilerplate the user didn't ask for.

### Output format

After cleanup, produce a brief report:

```
## Deslop report

### Removed
- <what was removed and why, one line each>

### Changed
- <what was adjusted and why, one line each>

### Kept (and why)
- <anything that looked like slop but was intentional, with justification>
```

If the diff is already clean, say so explicitly — "No slop found."

---

## Proactive loop — Research → Plan → Execute → Review → Revise

Use this when starting a new AI-assisted coding task. The goal is to prevent
slop from entering the PR rather than cleaning it up afterwards.

### 1. Research

Narrow the problem before writing a single line.

- Which files are relevant? Read them.
- What patterns already exist in the codebase? (naming, error handling, logging)
- Where are the trust boundaries? (what is validated, and where)
- What assumptions does this part of the code make?

Output a short context summary:

- Relevant files
- Key constraints and patterns
- Open questions (and answers)

Use this summary as your prompt context for the next steps.

### 2. Plan

Turn the research into intent. A good plan stops slop before the model
generates it.

- What must change? What must _not_ change?
- What naming and style conventions apply?
- What error-handling pattern does the codebase use?
- Are comments needed? At what level of detail?
- What abstractions already exist that should be reused?

Review the plan the way you would review an architecture decision — if
something feels off here, it is cheap to fix.

### 3. Execute

Let the AI work, but narrowly. Scope each prompt to the plan. Avoid open-ended
"implement this feature" prompts without constraints.

Good execution feels boring. If the output surprises you, something was
under-specified in the plan.

### 4. Review

Apply the reactive checklist above to everything that was generated. Then ask:
"Does this feel like it belongs here?"

Also verify:

- Tests pass
- Linting is clean
- Code matches the plan
- Style matches the file

### 5. Revise (the step most people skip)

When output doesn't match expectations, identify the root cause:

- What context was missing?
- What rule wasn't explicit enough?
- What assumption did the model make?

Then feed the learning back:

- Update project rules / `.cursor/rules` / system prompts
- Update agent instructions or slash commands
- Document the pattern so it doesn't recur

This step compounds. Each revision makes the next PR cleaner than the last
without any extra effort at generation time.

---

## Quick reference — what not to write

```python
# ❌ Comment restating the code
# Get the user by ID
user = get_user(user_id)

# ✅ No comment needed — the code is self-explanatory
user = get_user(user_id)

# ❌ Over-defensive guard inconsistent with the codebase trust model
def process(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("value must be str")
    if len(value) == 0:
        return ""
    return value.strip()

# ✅ Trust the caller; validate at the boundary, not deep inside
def process(value: str) -> str:
    return value.strip()

# ❌ Premature abstraction
class BaseProcessor(ABC):
    @abstractmethod
    def process(self, value: str) -> str: ...

class StringProcessor(BaseProcessor):
    def process(self, value: str) -> str:
        return value.strip()

# ✅ Just write the function
def process(value: str) -> str:
    return value.strip()
```

```typescript
// ❌ Type escape
const result = (someValue as any).property;

// ✅ Fix the type
const result = (someValue as MyType).property;

// ❌ Vibe extra — logging nobody asked for
console.log("Processing user", userId);
const user = await getUser(userId);
console.log("Got user", user);

// ✅ Just the code
const user = await getUser(userId);
```

---

## Key principle

The goal is not "remove all AI fingerprints". The goal is code that reads as
if a thoughtful engineer who knows this codebase wrote it. Sometimes that
means keeping a guard or a comment — but only when it genuinely serves the
reader.

When in doubt, delete it and see if anything breaks.
