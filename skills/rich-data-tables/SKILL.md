---
name: rich-data-tables
description: Use whenever building a UI table, list view, or dashboard panel showing records with amounts, dates, or statuses (invoices, tickets, orders, tasks, leads, log entries, etc.) — in React/HTML/artifacts, TanStack Table column defs, or when writing/reviewing component code for one. Consult before rendering a "flat" table (raw columns, no aggregation, no visual encoding), even if the user just says "make a table" or "show this data" — a bare table is rarely the best answer once rows carry a magnitude, a due date, or a status. Also use when asked to "make this table nicer", "more like a dashboard", or to add KPIs/summary above a table.
---

# Rich Data Tables

Turns a flat list-of-records table into a scannable dashboard panel. The default failure mode is
dumping rows 1:1 from the data source into a table — technically correct, but it forces the human
to do the aggregation, comparison, and prioritization in their head. This skill encodes that work
into the UI instead.

## When NOT to bother

Skip all of this for: small lookup tables (<5 rows), pure reference data with no magnitude/urgency
dimension (e.g. a list of country codes), or when the user explicitly asks for a plain/export-style
table (e.g. "give me a CSV-like table" or "just the raw data").

## The five upgrades, in priority order

Apply as many as are relevant — don't force ones that don't fit the data.

### 1. Summary strip above the table
Before listing rows, compute and show 3-5 aggregates as a header strip: total, count, the biggest
item, a "how many exceed threshold X" bucket, an average/age. This is the single highest-value
change — it answers "how bad/big is this overall" without reading every row.

- Pick aggregates that answer the question the table exists to answer (payments due → total
  exposure, biggest exposure, near-term due count; tickets → open count, oldest, SLA breaches;
  orders → total value, largest order, count above a size threshold).
- Format big numbers with locale grouping (e.g. 190,199 or 190'199, not 190199), and include the
  unit/currency only where it's not implied by context.
- Give each stat a one-line label above it, not just a bare number.

### 2. Relative + absolute dates together
Never show a bare ISO/absolute date alone when the date implies urgency (due dates, deadlines,
SLA). Pair the absolute date with a small pill: "in 3 days" / "overdue 2d" / "due tomorrow". Compute
the relative delta from "now", not from row order.

### 3. Encode magnitude inline, not just as a number
For any amount/quantity column, add a lightweight inline bar showing that row's share of the
relevant total (row_value / total_or_max), plus the percentage as small muted text next to it.
Color the bar by magnitude band (e.g. gray < 5%, orange 5-25%, red > 25%) so outliers are visible
without reading numbers. This is what turns "90,413" into "oh, that's half the total."

### 4. Status as a badge, not a raw value
Any enum/status/stage field (approval stage, ticket state, priority, risk level) becomes a colored
dot + label (green "None"/"Open", amber "Warning", red "Critical") — never a bare code like `0`,
`1`, `2`. Keep the color mapping consistent with the magnitude bands in #3 if both exist, so red
always means "needs attention" across the whole panel.

### 5. Hoist constant/low-cardinality columns out of the row grid
If a column is constant (or near-constant) across all visible rows — a company ID, a currency, a
region filter that's already applied — don't repeat it 13 times. Move it into the panel title or
subtitle (e.g. "13 open items · Region 3") and drop the column. This reclaims horizontal space
for #2 and #3.

## Column ordering & emphasis

- Lead with the identifier (doc/record number), then dates, then the decision-relevant column last
  (amount, status) — right-aligned and bold, since that's what the eye should land on last, moving
  left to right like a sentence ending in the punchline.
- Bold only the number itself, keep the currency/unit prefix muted/smaller.
- Right-align all numeric columns; left-align everything else.

## Beyond columns: spacing, type, icons, states, dark mode

The five upgrades fix *what* the table shows. These fix *how it reads* — skip a spreadsheet look
even when the data itself is already well-encoded.

- **Spacing**: use whitespace, not grid lines, to separate rows and cells — reserve borders for
  where they carry meaning (a totals row, a section break). Keep padding/gaps on a 4px scale (4,
  8, 12, 16, 24px) so row height and cell padding stay visually consistent across the panel; this
  is also what makes a `grid-template-columns` summary strip line up with the table below it.
- **Typography**: one sans-serif family for the whole panel; keep the size range narrow (a dense
  table rarely needs anything above ~20-24px, reserved for the summary strip's numbers). Inside a
  cell that stacks two pieces of information — a primary value and a secondary detail, like the
  date pills in upgrade #2 — make the primary line bigger/bolder and the secondary line smaller and
  muted, the same contrast the summary strip uses between its label and value.
- **Icons over labels**: where a column is really encoding a small fixed vocabulary (a direction,
  a channel, a file type), a same-size icon reads faster than a text label and saves column width —
  but only when the icon is unambiguous without a legend; keep the text label if you're not sure.
  Size icons to match the surrounding line-height (commonly 16-24px) so rows don't jitter.
- **Interactive states**: if a row or action button is clickable, show it — a hover background on
  the row, a pointer cursor, a subtle affordance (chevron, underline on hover) — don't rely on the
  user guessing. Any button in the table (sort, row action, "copy") needs its default/hover/
  active/disabled states defined, and a loading state if it triggers an async action. A brief
  micro-interaction (a small "Copied" chip that fades in/out) is worth it for actions whose result
  isn't otherwise visible.
- **Dark mode**: don't just invert — shadows read as murky on dark backgrounds, so give cards depth
  by making them a step *lighter* than the page background instead of relying on a shadow. Desaturate
  status colors (badges, magnitude bars) a notch from their light-mode values so they don't glare;
  keep the same hue mapping (red still means "needs attention") so meaning doesn't shift between
  themes.

## Implementation notes (TanStack Table)

TanStack Table is headless — it gives you rows/columns/sorting/pagination state, you own all
rendering. That maps cleanly onto the five upgrades:

- **Summary strip**: compute aggregates from `table.getPreFilteredRowModel().rows` (or
  `getCoreRowModel()` for the full unfiltered set) — never from `getRowModel()` alone, since that's
  post-pagination and only reflects the current page. Do this once outside the `<table>` render,
  as plain derived values (`useMemo` over the raw data array is simplest, or reduce over
  `table.getCoreRowModel().rows` if you need it post-filter).
- **Magnitude bars & badges**: put the visual encoding in the column's `cell` renderer, not in the
  raw data. E.g. `columnHelper.accessor('amount', { cell: info => <AmountCell value={info.getValue()} total={grandTotal} /> })`.
  Keep `grandTotal` (or whatever the bar is relative to) computed once and passed in via closure or
  `table.options.meta`, not recomputed per cell.
- **Status badges**: same pattern — `cell: info => <StatusBadge code={info.getValue()} />`, with the
  color-code mapping defined once as a shared lookup, reused by both the badge and any magnitude
  band coloring so red means the same thing everywhere in the panel.
- **Relative date pills**: format in the `cell` renderer too (e.g. via `date-fns`
  `formatDistanceToNow`), computed from `Date.now()` at render time — don't store the relative
  string in the data, since it goes stale.
- **Hoisting constant columns**: check cardinality before defining the column — if every row has
  the same value for a field, don't give it a `columnDef` at all; render it once in the panel title/
  subtitle instead. (Simple check: `new Set(data.map(d => d.field)).size === 1`.)
- **Totals row**: if you want a totals footer, TanStack Table supports this natively via each
  column's `footer` — compute it the same way as the summary strip (from full data, not the page).
- Mini inline bars themselves don't need a charting library — a `<div>` with `width: {pct}%` inside
  a fixed-width track, colored by band, is enough. Reserve a real charting lib (Recharts, Tremor)
  for the summary strip only if it needs an actual chart shape (sparkline, trend line).

## Quick self-check before shipping a table

- [ ] Is there a summary strip, or did I just render rows?
- [ ] Do due/deadline dates have a relative pill next to the absolute date?
- [ ] Does every amount column have a visual magnitude cue (bar/color), not just digits?
- [ ] Are status/enum columns colored badges, not raw codes?
- [ ] Did I drop columns that are constant across all rows into the header instead?
- [ ] Does spacing come from whitespace/padding (4px scale) rather than boxing every cell in borders?
- [ ] Within any two-line cell, is the primary value visually heavier than the secondary detail?
- [ ] Do clickable rows/buttons show hover/active/disabled states, not just a default look?
- [ ] If dark mode exists, do cards read as lighter-than-background instead of relying on shadows, and are status colors desaturated rather than full-brightness?
