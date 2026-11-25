---
name: bms-ui-review
plugin: ui
description: >
  Whole-app UI review of a BMS web app: static checks on the source (shared package versions, wording,
  tokens, components), a crawl of every screen, then parallel reviewers and one ranked issue list. Use for
  "review the whole UI", "ui review", "ui audit", "go through all screens", "find UI inconsistencies", or
  before a release. One page or one change: `design-review`.
---

# BMS UI review

> If the repo has a `DESIGN_REVIEW.md`, read it first; its rules take precedence over this skill.

A dry run: it reports and changes nothing, neither the code nor the app's data. Fixing is a separate task, once the
user has picked from the report.

Checks a BMS web app twice and returns **one ranked list of issues**: the **source files** (static, no app needed)
and **every screen** of the running app (rendered). You orchestrate: run one script, give its batches to parallel
reviewers, then verify, merge and rank. The checklist for one screen is `design-review`
("What to Check"); this skill adds the sweep, the automatic checks and the **comparison across screens**, which is
where inconsistencies show up.

## Effort

- **quick** (a change touched a few screens, or the user asks for a fast look): steps 1-2 with `--variants` the one
  the change risks most and `--routes` the touched paths, one reviewer, no explorers.
- **full** (default for "the whole UI", a release, an audit): every step below. Expect one prepare run of 10 to 15
  minutes (the crawls run at once) and 5 to 8 subagents; on a machine short of memory, run the app's backend elsewhere.

## 1. Read what the app says about itself

`DESIGN.md` / `DESIGN_GUIDELINES.md`, `PRODUCT.md`, the tokens in the app's CSS, the `bms-frontend-design` skill (BMS
red, radius scale, Heroicons) and the `bmsui` skill with `@bmsuisse/ui`'s `CATALOG.md` (the shared components and the
states they cover: `EmptyState`, `ErrorState`, `ConfirmDialog`, `DataGrid`...; step 2 writes its path in the
manifest, do not search the disk for it). The variants (light, dark, the longest language) are step 2's job. Two
things it does not decide: an app that needs sign-in gets a Playwright `storage_state` of a test user (or the
app's dev-auth mode), and an app that is not desktop only (PRODUCT.md) gets a second run at `--width 390`.

Use test or sample data (a sandbox, a seeded dev database), never production, and never a real person's account:
the crawl opens every screen it can reach and the screenshots end up in files and subagent prompts.

**Read the UI-fix history** (`git log --since=6.months --format=%s | grep -iE 'fix\((ui|frontend|i18n|a11y)|align|overflow|translat|dark'`).
What broke before breaks again, and most of it broke in a state, not on a first load: a filter applied, a hover, a
drawer opened from a row, a long language. Those states are what the explorers in step 3 must reach.

## 2. Prepare: one command

Start the app the repo's own way (its `just` recipe or README), then, from the repo (its own Playwright, when it has
one, has its browser installed; else `uv run --with playwright python`):

```bash
uv run python <this skill's folder>/scripts/prepare.py http://localhost:5173 --repo . --out scratch/ui-review
```

**Await it** in the call that starts it, with a timeout of 30 minutes (a REPL `$` command waits up to 2 hours; the
Bash tool stops at 10 minutes, so there run it in the background and wait for its exit). Never start the crawls
yourself and move on: a profiled run that did started them 13 minutes late. The crawls run in parallel, as tabs of one shared
Chromium (`--browsers separate` for one Chromium each), and share a claims folder, so no screen or popup is done
twice (`--workers`, default from CPUs and free memory). On OneView, 6 workers took the prepare step from 9.6 to about
4-5 minutes with the same coverage, and the shared browser used 3.9 GB at peak against 5.5 GB for separate ones. The
app's backend is the limit beyond that: 6 tabs ran 2.4 times faster than 1, not 6.

In one process it finds the frontend source and its routes (TanStack `createFileRoute`, React Router `path`), the
localStorage theme and language keys and the UI languages; opens the app once to find real ids for the `$param`
routes in its links and to check that dark mode and the language key really apply (dark through the browser's
preference is captured in the light crawl, `--also-dark`; through a stored setting, in its own crawl); then runs
`scan.py` and one `crawl.py` per variant at the same time and waits. Options: `--variants light dark de`,
`--routes /r/sales` (real paths: start paths and ids), `--max-screens`, `--theme-key` / `--lang-key` when the
manifest shows the wrong one; any `crawl.py` option (`--storage-state auth.json`, `--exclude`) goes to every crawl.

It writes `manifest.json` (keys, variants run, routes covered and **not covered** with why, the catalog path, image
and text sizes, seconds per step) and `batches.json` (step 4). Read the manifest first: a route not covered that
matters gets a real path through `--routes` and a second run. After a change to the scripts: `selfcheck.py`.

**The scan** (`scan.md`; no browser) lists, by file and line:

- **shared packages**: each `@bmsuisse/*` package behind the latest on npm (the installed version, else the declared
  range). Read this first. A bug the newer package fixes is one finding, "update `@bmsuisse/ui` 0.25 -> 0.33", not
  the app's own bug on every screen (from 0.30 `@bmsuisse/ui` translates its own components, for one). A 0.x minor is
  a breaking range: say "read the changelog", not just "bump";
- **wording**: one word for two meanings in a translation (fr `annuler` for both Cancel and Discard), two words for
  one action within a language (Delete / Remove, Cancel / Discard / Close), one message in two forms ("Add member"
  and "Add a filter", "Saved." and "Saved"), values left equal to English and missing keys, `du` next to `Sie` (or
  `tu` next to `vous`, help pages included), a count with no plural form ("1 fields"), British next to American
  spelling, several wordings for "no value", repository paths or tool names in help text;
- **code**: raw colours instead of tokens, icons from another set than Heroicons, native controls where the catalog has
  a component (`<input type="date">`, `<table>`, `window.confirm`), `DataGrid` without the app's language, a button
  disabled for invalid input with no reason, controls shown on hover only, a colour dot with no label, fonts under 11px
  (charts and canvas too), inline px sizes, click handlers that navigate where a link belongs, a third-party widget
  (diagram, map, editor) with no dark override, and the contrast of the token pairs (`x` on `x-foreground`, muted text)
  in light and dark.

What the code shows is found here in seconds and for every screen, also the ones no crawl reaches; the crawl is for
what only rendering shows (overlaps, positions, a blank card, charts, contrast of one-off colours).

It sees every string and component, also those no crawl reaches (dialogs, toasts, errors). Its output is leads: open
each line and drop what is deliberate (a print stylesheet and a chart library need px and raw colours, token
definitions are raw colours, "Remove" from a list and "Delete" for good are two meanings). What holds goes in the
report, and a rule that should keep holding goes in the app's CI (a lint rule, a unit test over the locale files).

**The crawl** follows links (query strings kept: `?page=2` is a screen) from the routes, keeps one screen per route
pattern, and never submits a form. Per screen it writes a full-page `.png`, a 1000 px `.thumb.jpg` of the window, a
`.txt` of the visible text tagged by role (headings, breadcrumb, buttons, links, labels, table headers and three
rows, alerts, the rest deduplicated) and a crop around each automatic finding. In the light crawl it opens up to 5
popups per screen (`aria-haspopup` triggers and the `--open-label` buttons; destructive labels are never opened) and
5 dropdowns (from the keyboard, so nothing is picked), captures each once and closes it with Escape. A native
`<select>` cannot be captured open; the scan reports it.

`report.json` and `summary.md` hold, per screen, the automatic findings (page overflow, scrollbars inside cards,
controls off one line, a control drawn over text or another control, popups past the window edge, list options cut
with no tooltip, clipped text, leaked `undefined`/`NaN`, raw i18n keys, low contrast, unnamed controls, disabled
controls that do not say why, console errors, HTTP 4xx/5xx, redirects), a **style inventory** (font sizes, radii,
button heights, every button and link label) and the **synonyms in use** with their screens.

**Explorers** (full effort): a crawl sees each screen as it first loads. For the 3 to 5 flows the fix history and the
product doc point at, spawn one explorer per flow, **in the same message that starts `prepare.py`** (they need only
the running app and the route files, not its output; started after it, they were the longest part of a profiled
run), `general-purpose` with `model: "sonnet"`, each with a budget of 6 minutes:
"Drive <flow> on <url> with a short Python Playwright script (skill `playwright-python`): reach <the states: a filter
applied, a row opened, hover and focus on its controls, the long language>; many states can be set through the URL
(filters, pages, tabs), which is quicker and repeatable. Capture each state in <variants> into <folder>/<flow>/. Never
save, submit or delete; reset what you changed. Stop at 6 minutes with what you have. List the files with one line
each." Their screenshots go to the reviewers with the crawl's.

## 4. Review in parallel

Images are the main token cost of a review, and most findings need no pixels: copy, translations, leaks, missing
values and wording show in the text. So `batches.json` has two kinds of batch, grouped by area. A **text** batch holds
each screen's `.txt` in light and the long language, its dialogs' text and the findings no picture is needed for;
its reviewer reads no image. A **visual** batch holds thumbnails only where pixels can show something new: a screen
with a layout finding, a chart, map or canvas, the first screen of each route and each kind of popup; dark and the
long language only where their findings differ from light. `shared` lists once the findings on many screens (the
shell's). On OneView, 8 screens a variant: 59 full pages (about 90k tokens) became 30 thumbnails and 51 text files
(about 31k).

Spawn one reviewer per batch, **in one message**, `general-purpose` with `model: "sonnet"`, plus the **consistency
reviewer**. Each brief holds:

- its batch from `batches.json` (paths, findings, why each image was picked) and the scan findings for the source
  files behind those screens; a visual reviewer opens a full-page `.png` only when the thumbnail cuts off what it
  needs;
- the app's design source from step 1 (paths), `design-review`'s "What to Check", `bms-frontend-design` and the
  `CATALOG.md` path;
- the output contract below, and: "Read every file of your batch. Report only what you can see or measure; cite the
  file."

What each reviewer looks for (in addition to the design-review checklist):

| Area | Look for |
|---|---|
| Copy | typos, mixed languages on one screen, untranslated strings, select options and status values, abbreviations and badges with no tooltip (YoY, pts, Δ), Title Case vs sentence case, one thing named two ways |
| Typography | sizes and weights outside the scale, headings that differ between equal screens, numbers not tabular or not in Swiss format (1'234.50) |
| Sticky parts | a sticky header, toolbar or action bar that covers table headers, focused fields or the last rows when the page scrolls |
| Layout | misaligned edges, uneven gaps, page titles and toolbars at different heights or places on equal screens, equal parts that do not line up (two panes of one drawer, a row of controls, labels and values across tiles), overflow, clipped text, a scrollbar inside a card |
| Colour | brand red used beyond its role, raw colours instead of tokens, low contrast, dark-mode surfaces or third-party widgets (maps, diagrams) that miss the theme |
| Components | two styles of one control (buttons, inputs, tabs, badges, tables), mixed icon families, anything hand-made where `CATALOG.md` has a component (name it in the fix: `DateInput`, `EmptyState`, `DataGrid`) |
| Leaks | technical notes (which server or query answered), internal ids, stack traces, `[object Object]`, a generic "not found" where the real cause is known, debug labels |
| Missing values | one display for no value across the app (`–`, blank, "no data", 0, "not set"): the same absence shown two ways is a finding |
| States | an error that leaves a blank screen or loops, feedback that is easy to miss, a failed part that does not fill its place, missing empty, loading or error states, content that blanks out on refetch, disabled controls that look active or do not say why, no active item in the nav |
| Accessibility | unnamed controls, focus not visible, colour as the only signal, a button that navigates where a link belongs |

The **consistency reviewer** gets the style inventories (`summaries`), the synonym lists, the scan, `shared`, and
one thumbnail per area. It compares the app's shell with the other BMS apps through `bms-frontend-design` (logo and wordmark size,
sidebar width, header height, radius scale); decides for each synonym set whether it is one meaning named two ways (a
finding) or two meanings that need two words (fine); and compares screens: one page-header pattern or several, the
same action in the same place, how many font sizes, radii and button heights are in use (a consistent UI keeps 3 to 5
of each).

Output contract, one line per finding, nothing else:

```
<P0|P1|P2|P3> | <category> | <screen path(s)> | <what is wrong, concretely> | <fix> | <screenshot file>
```

## 5. Verify, merge, rank

- **Verify** every P0 and P1 through one verifier subagent (`general-purpose`, `model: "sonnet"`), never in your own
  context, where each image stays for every later turn. Give it the lines with, for each, the finding's `crop` from
  `batches.json` (else the thumbnail the reviewer cited); it returns, as text, "kept" or "dropped: why" per line.
  Drop what it cannot see, and what a language's own rules require (French puts a space before `:`, German
  capitalises nouns).
- **Shared package or app**: a finding the newer `@bmsuisse/*` version fixes becomes the one "update" finding.
- **Content is not code**: text from the data or the sample content in one language (product names, titles users
  typed) is a content task; report it once as such.
- **Merge** duplicates: the same problem on ten screens is one finding listing ten screens, which is a pattern.
- **Rank**: P0 broken or blocking (error screens, invisible text, data that leaks `undefined`), P1 a WCAG AA failure or
  a clear inconsistency a user notices, P2 polish with visible effect, P3 nits.

## Report

Write it to `scratch/ui-review/REPORT.md` (or wherever the repo keeps scratch output); post it to a PR or an issue
only when asked.

```markdown
# UI review: <app>, <date>, <commit>
Screens: <n> in <variants>, <n> dialogs, <n> explored states; not covered: <states, roles, languages not reached>

## Update first
<the @bmsuisse/* packages behind, and which findings below they probably fix; "none" when up to date>

## Summary
<2-3 sentences: overall state, the main patterns>

## Issues
| # | Sev | Category | Screens | Issue | Fix | Evidence |
|---|-----|----------|---------|-------|-----|----------|

## Patterns
<recurring problems with one root cause, e.g. "page headers: three variants across 14 screens">

## CI checks to add
<the scan rules that hold for this app, as lint rules or tests, so the same issues cannot come back>

## What is consistent
<what to keep>
```

## Common mistakes

- Reviewing first loads only: the bugs the fix history shows live in states (a filter applied, a hover, a long language).
- Reviewing one variant only: most contrast problems live in dark mode, most overflow in the longest language.
- Reporting a bug the newer `@bmsuisse/*` package fixes as the app's own, on every screen.
- Taking crawl and scan findings as verdicts: open the screenshot or the line first.
- Reporting each occurrence: group by cause, list the screens.
- Judging against generic taste instead of the app's DESIGN.md and the BMS identity.
- Crawling production or with a real account.
- Running the crawls by hand, or in the background without waiting for them: `prepare.py`, awaited.
- Reading screenshots in the orchestrator's own context: reviewers and the verifier read them and return text.
