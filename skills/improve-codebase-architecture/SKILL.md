---
name: improve-codebase-architecture
description: >
  Scan a codebase for architectural friction and propose "deepening"
  refactors that turn many shallow modules into fewer deep ones, so the code is
  easier to test and easier for humans and AI to navigate. Presents candidates
  as a visual HTML report, then walks through the chosen one. Use whenever the
  user wants an architecture review, says the codebase is hard to navigate or
  test, has too many tiny files or pass-through layers, asks "where should we
  refactor", "what is the biggest design smell", "improve the architecture",
  "find refactoring opportunities", "make this more testable", or wants to
  decide where a module boundary or seam should go — even if they never say
  "architecture". For line-level readability use clean-code instead.
---

# Improve Codebase Architecture

Find places where the structure itself causes friction and propose **deepening
opportunities**: refactors that replace several shallow modules with one deep
module (a lot of behaviour behind a small interface). The payoff is code that
is cheaper to change, testable through one interface, and quick for a reader or
an AI agent to navigate without bouncing across many files.

The vocabulary matters: load the `codebase-design` skill first and use its terms (**module, interface, depth, seam, adapter, leverage,
locality**) exactly. Words like "component", "service", "API" and "boundary"
are overloaded and blur the point of the review. For the domain itself, use the
names the project already uses (glossary, README, ADRs).

Idea adapted from Matt Pocock's `improve-codebase-architecture` skill.

## Process

### 1. Scope before you scan

Deepening pays off where code keeps changing, so look where the churn is.

- If the user named a direction (a module, subsystem, pain point), take it.
- Otherwise read `git log --oneline` back a good stretch and find the hot
  spots: files and areas that keep coming up. Let those pull your attention
  first. If changes are scattered with no hot spot, widen the net.
- Read existing architecture notes first: `docs/adr/`, `GLOSSARY.md`,
  `CLAUDE.md`, README. Decisions recorded there are not yours to re-litigate.

### 2. Explore for friction

Delegate the walk to a sub-agent if the codebase is large; it keeps file dumps
out of your context. Explore organically, noting where understanding hurts:

- Understanding one concept means jumping between many small modules.
- A module's interface is nearly as complex as its implementation (**shallow**).
- Pure functions extracted "for testability" while the real bugs hide in how
  they are called (no **locality**).
- Tightly coupled modules leak across their seams.
- Parts that are untested, or can only be tested by reaching past the interface.

Apply the **deletion test** to every suspect: imagine deleting the module. If
the complexity vanishes, it was a pass-through (a deepening candidate: merge or
remove it). If the complexity reappears across many callers, it was earning its
keep — leave it.

If `codegraph` is indexed in the repo, `codegraph callers`/`callees` give real
fan-in and fan-out: a module with many callers and one-line bodies is shallow,
and `codegraph impact <symbol>` sizes the blast radius of a deepening. Don't
install or index it just for this review without asking (it writes `.codegraph/`).

Back suspicions with evidence from `duplicatecode` (`uvx duplicatecode scan . --skip-tests`):
duplicated knowledge across modules points at a missing or misplaced seam. See
[references/duplicate-detection.md](references/duplicate-detection.md) for
commands and how to read the results. Keep it offline-only unless the user
approves hosted embeddings.

For each candidate, classify its dependencies (in-process, local-substitutable,
remote-but-owned, true external) using the dependency categories in `codebase-design` (DEEPENING.md), because that
decides how the deepened module will be tested.

### 3. Present candidates as an HTML report

Show the findings visually; architecture is easier to judge from a before/after
picture than from paragraphs. Follow [references/html-report.md](references/html-report.md).
Write one self-contained file to `$TMPDIR` (fall back to `/tmp`), not into the
repo, so nothing needs cleaning up, then open it (`open <path>` on macOS) and
tell the user the absolute path. If opening is blocked in the sandbox, just give
the path.

Each candidate gets: files involved, problem (one sentence), solution (one
sentence), wins, before/after diagram, and a recommendation strength
(`Strong`, `Worth exploring`, `Speculative`). End with a **Top recommendation**.

If a candidate contradicts an existing ADR, surface it only when the friction
is real enough to justify reopening it, and flag that clearly. Don't list every
refactor an ADR forbids.

Do **not** propose interfaces yet. Finish by asking: "Which of these would you
like to explore?"

### 4. Explore the chosen candidate

Once the user picks one, interview them to settle the design before touching
code. Ask in rounds: every question whose prerequisites are already settled,
numbered, each with your recommended answer worded so "yes" accepts it. Cover
constraints, dependencies, the shape of the deepened module, what sits behind
the seam, and which tests survive. Look up facts yourself (read the code); only
decisions go to the user. Stop when no open question is left.

- To compare alternative interfaces, use the *design it twice* pattern in
  `codebase-design` (DESIGN-IT-TWICE.md) (parallel sub-agents, radically different designs, then your own
  opinionated recommendation).
- If the user rejects a candidate for a lasting reason a future reviewer would
  need, offer to record an ADR so it isn't re-suggested. Skip ephemeral reasons
  ("not now").
- If a new module is named after a concept the project has no word for, offer
  to add that term to the glossary.

### 5. Hand off, don't refactor blindly

This skill produces a decided design. Implementing it is a separate step: do it
in small verified steps with tests at the new interface, and keep refactor and
behaviour change in separate commits (see `clean-code`). Replace old shallow
unit tests rather than layering new ones on top.
