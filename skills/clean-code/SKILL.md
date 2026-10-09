---
name: clean-code
description: >
  Language-agnostic, pragmatic clean-code principles for writing and refactoring
  code at BMS: naming, function size and shape, control flow, error handling,
  abstraction, duplication, structure, and safe refactoring. Use whenever the
  user is writing new code, cleaning up or refactoring existing code, reviewing
  readability, or says the code is messy, hard to read, too long, too nested,
  or over-engineered — even if they never say "clean code". Trigger on: "clean
  code", "refactor", "clean this up", "readability", "simplify this function",
  "split this function", "too nested", "bad naming", "code smell", "tech debt",
  "make this maintainable". Defers to coding-guidelines-python / -typescript /
  -react / -sql for language specifics, code-comments for comment style, and
  deslop for removing AI noise from a diff.
---

# Clean Code

Code is read far more often than it is written, so optimize for the next
reader — who is usually you in three months, without the context you have now.
These rules are opinionated and pragmatic: each one exists because it removes a
real cost. When a rule makes a specific piece of code worse, break it and move
on; don't chase purity.

Language-specific style lives in the `coding-guidelines-*` skills. Comment
style lives in `code-comments`. This skill covers what holds in every language.

## Core principles

1. **Make it obvious, not clever.** If a reader must pause to decode a line,
   rewrite it. Boring code is cheap to maintain.
2. **Match the surrounding code.** Consistency with the existing file beats
   your preferred style. Read neighbouring code before writing.
3. **Delete before you add.** The cheapest code to maintain is code that does
   not exist. Remove dead code, unused params, and speculative features.
4. **Leave it a little better, and no wider.** Clean what you touch; don't
   rewrite what you were not asked to change.

## Naming

Names carry most of the meaning, so spend time on them.

- Name by **what it is or does in the domain**, not how it is stored:
  `overdue_invoices`, not `list2` or `data`.
- Functions are verbs (`calculate_margin`), values are nouns, booleans read as
  questions (`is_active`, `has_discount`). Avoid negated booleans (`not_ready`).
- Length matches scope: `i` in a 3-line loop is fine; a module-level name needs
  to stand alone.
- One word per concept across the codebase (don't mix `fetch`/`get`/`load` for
  the same idea).
- Don't encode types or noise (`customerList`, `DataManager`, `utils`). A
  vague name like `process` or `handle` usually means the function does too much.
- When refactoring, renaming a vague function (`proc`, `calc`, `handle`) is
  usually the highest-value change. Find its callers first: rename them too,
  or keep the old name as a thin alias and say so, never leave the vague name
  because renaming felt risky.
- Use the business vocabulary the team already uses, in the language the
  codebase already uses.

## Functions

- **Do one thing at one level of abstraction.** If you can describe it only
  with "and", split it. Top-level functions read like an outline; details sit
  in helpers.
- **Keep them short enough to hold in your head**, roughly what fits on one
  screen. Length is a symptom; the real test is whether you can name every piece.
- **Few parameters.** More than ~3 means a missing concept: group related
  arguments into a single object. Avoid boolean flag parameters — they mean
  two functions in one; split them.
- **Prefer pure functions.** Same input, same output, no hidden state. Push
  I/O and side effects to the edges so the core logic is trivially testable.
- **Separate commands from queries.** A function either changes state or
  returns information, not both in a surprising way.
- Return early to keep the happy path unindented (see below).

## Control flow

- **Guard clauses over nesting.** Handle invalid or trivial cases first and
  return; the main logic then stays flat. Aim for at most 2 levels of
  indentation in typical code.
- Extract complex conditions into a named boolean or function:
  `if is_eligible_for_discount(order)` beats a four-clause `if`.
- Replace long `if/elif` chains on a type with a lookup table or polymorphism
  only when the chain is growing; two or three branches are fine as they are.
- Avoid magic numbers and strings: give them a named constant that says why.
- Prefer declarative transforms (map/filter/comprehension) when they read
  clearer than a loop; use a plain loop when they don't.

## Error handling

Errors are part of the contract, not an afterthought.

- **Fail fast and loud.** Validate at trust boundaries (user input, API
  payloads, files) and raise immediately; inside the core, trust your types.
- Never swallow exceptions silently. Catch only what you can handle, and
  re-raise or log with context otherwise. A bare `except`/empty `catch` hides bugs.
- Use exceptions (or the language's error type) for failure, not sentinel
  return values like `None`, `-1`, or `""` that callers forget to check.
- Make error messages actionable: say what failed, with which value, and what
  was expected.
- Don't add defensive checks for states that cannot happen. They add noise and
  imply a danger that doesn't exist.

## Abstraction and duplication

**No duplication, but don't abstract too early.** Before writing something new,
check that it does not already exist (grep, `duplicatecode diff` on your change).
Before merging, run the duplicate gate below.

- **Rule of three.** Tolerate duplication twice; abstract on the third. The
  wrong abstraction is more expensive than copy-paste because every caller
  bends around it.
- Don't build for hypothetical futures: no interface with one implementation,
  no config for a value that never changes, no plugin system for one plugin.
- To find existing duplicates (or check a diff for re-implemented code), run
  `uvx duplicatecode scan . --skip-tests` or `git diff origin/main | uvx duplicatecode diff --repo .`.
- Duplication of **knowledge** (business rules, constants) is the dangerous
  kind — keep each rule in one place. Duplication of incidental shape is often fine.
- Prefer composition and small modules over deep inheritance hierarchies.
- A module should hide a decision. If changing one detail ripples through many
  files, the boundary is in the wrong place.

## Structure and files

- Group by **feature/domain**, not by technical layer, when the project grows.
- Keep related code close; a reader should rarely have to jump across the repo
  to understand one function.
- Dependencies point inward: business logic does not import framework, DB, or
  HTTP details; the edges adapt to it.
- **Keep files small.** Split by reason to change first; line limits are only
  the backstop that catches growth. BMS limits per file: `.py`/`.sql` 1200,
  `.ts` 600, `.tsx`/`.vue` 900, `.md` 500, `.sh` 100 (tests get 1.5x), with a
  warning at 75% of the limit. A file near its limit is a signal to extract a cohesive
  module, not to reformat. Generated code is exempt.
- No grab-bag `utils`/`helpers`/`common` dumping grounds; put helpers next to
  the code that uses them, or name the module for what it provides.

## Comments

Good code needs few comments; comments explain **why**, never **what**. If you
need a comment to explain what a block does, extract it into a named function
instead. Delete commented-out code (git remembers). For comment style, follow
the `code-comments` skill.

## Refactoring safely

Refactoring changes structure, not behavior — so prove behavior did not change.

1. **Have a safety net first.** If there are no tests around the code, write a
   characterization test that pins current behavior before you touch it.
2. **Small steps, run tests after each.** Rename, extract, inline, move — one
   at a time.
3. **Never mix refactor and behavior change** in one commit or PR. Reviewers
   cannot tell what really changed.
4. **Stay in scope.** Don't reformat unrelated files; it buries the real diff.
5. Stop when it reads well. Further polishing is gold-plating. If the code is
   already clear, say so and change little or nothing: a no-op is a valid result.

## Enforce it with tooling

Rules that depend on reviewers noticing will decay, so every repo should have
the linter do the mechanical part. For Python repos, recommend the OneSales
ruff setup (explicit rule `select`, banned imports, absolute imports only, no
`print()`, targeted `noqa` only), and help the repo adopt it: see
[references/ruff-setup.md](references/ruff-setup.md) for the config, the
rationale, how to introduce it into a legacy codebase without one giant PR, and
the complexity check. Hook wiring is in the `prek` skill. When reviewing or
setting up a Python repo and `pyproject.toml` has no explicit ruff `select`,
suggest this. Frontend equivalents: Biome and `tsc` (`coding-guidelines-typescript`).

### Gates for size and duplication

Both are mechanical, so enforce them instead of relying on review:

- **File size**: `scripts/check_file_size.py` (stdlib, edit the `LIMITS` table):
  a prek local hook with `pass_filenames = true`, same as OneSales' `check-files`.
- **Duplication**: `uvx duplicatecode scan . --skip-tests --fail-on-found` in CI
  (offline, no embeddings), and `git diff origin/main | uvx duplicatecode diff --repo .`
  to catch a PR that re-implements existing code.

Hook entries, thresholds for adopting them in an existing repo, and how to read
duplicate reports are in [references/size-and-duplication.md](references/size-and-duplication.md).

## Smells that signal a problem

| Smell | Usual fix |
|-------|-----------|
| Function needs "and" to describe it | Split by responsibility |
| Deep nesting | Guard clauses, extract function |
| Long parameter list | Group into an object, or split the function |
| Boolean flag parameter | Two functions |
| Same `if type ==` chain in many places | Lookup table / polymorphism |
| Comment explaining a block | Extract + name it |
| Name needs a suffix like `2`, `New`, `Final` | Rename by purpose, delete the old one |
| Shotgun edits (one change touches many files) | Move the shared decision into one module |
| Dead code, unused params | Delete |

## How to apply this

When **writing**, aim for the simple version first and apply these rules as you
go. When **refactoring**, read the code, name the top two or three problems
(not twenty), fix those in small verified steps, and say briefly what changed
and why. When **reviewing**, report only issues that hurt readability or
correctness, with the location and a concrete fix — skip taste-only nitpicks.
Rank by severity (security and correctness before structure before style) and
keep the proposed next step proportionate to the code: for a 50-line class,
suggest pulling out the one or two seams that hurt (a pure validation function,
the mail call), not a repository/service/DI layering.
