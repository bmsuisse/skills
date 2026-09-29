---
name: bms-frontend-design
plugin: coding
description: >
  The BMS visual identity for internal web apps, built on the shared
  `@bmsuisse/ui` (sidebar/nav, form, dialog, and other primitives) and
  `@bmsuisse/datagrid` (`<DataGrid>`/`<TreeDataGrid>`) packages — plus the
  brand tokens (BMS red accent, background/surface scale, border-radius
  scale, typography) every app still has to define itself, and the
  Heroicons `24/outline` icon set with a curated concept-to-icon mapping.
  Use this whenever scaffolding a new internal BMS app's UI, building or
  restyling a sidebar/nav, picking colors for a new app, styling a data
  table or grid, choosing icons, making a layout responsive/mobile-friendly,
  or reviewing frontend code for visual consistency with other BMS apps.
  Trigger on requests like "make this look like our other internal tools",
  "add a sidebar nav", "what colors should I use", "style this table", "what
  icon should I use for X", "how do I make this responsive", or "set up the
  theme" for a BMS app — even if the user doesn't say "design system"
  explicitly. Supersedes generic frontend-aesthetic advice (e.g. "pick a
  bold, unique look per app") for anything under the BMS brand — the point
  here is consistency across apps, not differentiation.
---

# BMS Frontend Design

Visual conventions for BMS internal web apps. Most of the UI mechanics —
sidebar, nav rows, mobile drawer, resizable panels, data grid — already
live in `@bmsuisse/ui` and `@bmsuisse/datagrid` (public npm packages
published from the `bmsuisse/bmsui` monorepo, no private feed needed).
**Reach for those first; don't rebuild what they already do.** What's left
here: the brand tokens every app still defines itself (colors, radius,
type), and a few decisions the libraries deliberately leave to the app.

```
bun add @bmsuisse/ui @bmsuisse/datagrid
```

Assumes the Tailwind v4 + shadcn/ui setup `init-app-stack` scaffolds: CSS
variables in `src/index.css` consumed via `@theme inline`, a `.dark` class
variant. Define tokens there, not as hardcoded hex in components — that's
what makes dark mode and future rebrands (a different `--primary`) work for
free, and it's how `@bmsuisse/ui`'s components pick up your app's colors.

## Layout — left navigation

Use `Sidebar`, `SidebarNav`, `NavGroup`, and `NavItem` from `@bmsuisse/ui`
instead of hand-building a sidebar. Resizing (240px default, 180–420px
range, persisted via the `width`/`onWidthChange` props), the 56px
icon-only rail collapse with hover tooltips, active/hover/inactive row
states, and section-group labels with their own collapse chevron are all
built in — don't reimplement any of that per app.

What's still on the app:
- Define the tokens the components read:
  ```css
  --sidebar: #fcfcfc;        /* Sidebar background */
  --nav-primary: #DC001A;    /* BMS red — active-row highlight, see Brand colors */
  ```
- Compute `active` per row from your own router — `NavItem` has no router
  opinion (`active={pathname === "/overview"}`).
- Pick the icon per `NavItem` — see
  [`references/icons.md`](references/icons.md) for the concept-to-icon
  mapping.
- Persist `Sidebar`'s `width`/`collapsed` state yourself (e.g.
  `localStorage`) via the `onWidthChange`/`onCollapsedChange` callbacks —
  the component doesn't persist it for you.

## Responsive — mobile

Don't shrink `Sidebar` itself below `md` — its resize handle and
rail-collapse don't apply on mobile. Instead reuse the same
`NavGroup`/`NavItem` children inside a `Sheet` via the separately-exported
`SidebarNav` (see that component's doc comment). `ResponsivePanel` and
`useMediaQuery` (also `@bmsuisse/ui`) cover the general "different layout
below a breakpoint" case elsewhere in an app.

For anything you build by hand outside these components: use `100dvh`, not
`100vh` (avoids the gap/scroll-jank `100vh` causes as mobile browser chrome
appears/disappears), and pad with `env(safe-area-inset-*)` so content
doesn't sit under a notch or home indicator.

## Brand colors

**BMS red** is the signature accent: `#DC001A` (light) / `oklch(0.58 0.2 27)`
(dark). There are two legitimate ways to use it — pick one per app rather
than mixing them:

1. **Red as accent only** — keep the app's `--primary` a neutral navy
   (`#2e4a62` light / `#6B90B8` dark) for buttons and links, and reserve red
   specifically for `--nav-primary` (the sidebar active-state highlight).
   This is the more common pattern — it keeps red as a "you are here"
   signal rather than spraying it across every button.
2. **Red as primary** — set `--primary` (and `--ring`) to BMS red directly,
   for an app that wants to lead with the brand color everywhere (buttons,
   links, focus rings), not just in the nav.

Either way, define it as a CSS variable (`--nav-primary` and/or `--primary`),
never a hardcoded hex in a component.

Semantic colors follow the same hue-preserving pattern between light and
dark mode: keep the hue, raise lightness and saturation slightly for dark
backgrounds so they still read as the same color family.

| Meaning | Light | Dark (same hue, lighter) |
|---|---|---|
| Destructive / error | `oklch(0.56 0.22 27)` | `oklch(0.68 0.21 27)` |
| Positive / success | `oklch(0.62 0.14 150)` | `oklch(0.76 0.15 165)` |
| Warning | `oklch(0.72 0.14 70)` | `oklch(0.82 0.14 80)` |
| Info | `oklch(0.60 0.12 230)` | `oklch(0.76 0.13 245)` |

## Background & surface scale

Keep it to three tiers — page, card, muted — rather than the overlapping
`--surface`/`--surface-2`/`--surface-3` families that tend to accumulate
once a codebase has been through a few redesigns.

| Tier | Use for | Light | Dark |
|---|---|---|---|
| `--background` | Page/app shell | `#fcfcfc` (near-white) | `oklch(0.165 0.022 265)` |
| `--card` | Cards, panels, modals | `oklch(1 0 0)` (pure white) | `oklch(0.205 0.026 265)` |
| `--muted` | Chips, table headers, subtle fills | `oklch(0.975 0.002 250)` | `oklch(0.245 0.030 265)` |

Note that cards are *whiter* than the page background in light mode — that
subtle lift is what makes a card read as elevated without needing a shadow.

## Border-radius scale

Use one consistent scale everywhere instead of picking a radius per
component — `@bmsuisse/ui`'s own components (nav rows, buttons, cards) are
already built against these values, so anything you build outside the
library should match them too.

| Radius | Use for |
|---|---|
| 6px | Compact/xs controls |
| 8px | Default buttons, inputs, nav rows — the default |
| 12px | Cards, kanban-style cards, modals |
| 16–20px | Hero/feature cards, prominent panels |
| full (9999px) | Badges, pills, avatars, segmented controls |

## Typography

- **Inter** (variable font), falling back to `system-ui`. Base body size
  **~15px**, letter-spacing **-0.01em**, antialiased.
- Amounts, KPIs, and other numeric displays: tabular numerals
  (`font-variant-numeric: tabular-nums`) so digits align in columns. Use
  `@bmsuisse/ui`'s `KpiCard` for KPI tiles and `@bmsuisse/datagrid` numeric
  columns — both already apply this; the rule mainly matters for numeric
  displays outside those two.
- Number formatting: Swiss convention, not US. Format with the `de-CH`
  locale (`value.toLocaleString('de-CH', { minimumFractionDigits: 2,
  maximumFractionDigits: 2 })`) rather than hardcoding a comma separator —
  it renders the thousands separator as an apostrophe (`128'450.00`), which
  is what a comma would silently get wrong for a Swiss audience.
- Small "eyebrow" labels (section headers, table column meta): ~10–11px,
  bold/semibold, wide letter-spacing (~0.1–0.12em), often uppercase.

## Data grids

Use `<DataGrid>` / `<TreeDataGrid>` from `@bmsuisse/datagrid` for anything
grid-shaped (sortable/filterable rows, more than a couple dozen records) —
don't hand-build a `<table>` for it. The package already covers:

- **Zebra striping**: pass `zebra` — it's keyed off logical row index, not
  DOM position, so it stays correct under virtualization instead of
  flickering as rows mount/unmount during scroll.
- **Virtualization**: auto-enables above 100 rows (`virtualize` prop to
  tune the threshold), backed by `@tanstack/react-virtual`.
- **Numeric columns**: right-aligned header + cells and tabular numerals
  follow automatically from the column's `type` — no per-column styling
  needed.
- Column filters/sort, column resizing and visibility (`ColumnSelector`),
  row actions (`ActionsMenu`), sticky group headers, and cell editing.

Reach for the raw `Table`/`TableRow`/`TableCell` primitives (also in
`@bmsuisse/ui`) only for small, static, non-interactive tables — a settings
summary, not a data grid.

## Keeping the shared libraries current

Both packages move fast — check `npm view @bmsuisse/ui version` /
`@bmsuisse/datagrid version` (or `github.com/bmsuisse/bmsui`'s commit
history) before assuming a capability is missing, and bump the
`package.json` version rather than working around a gap that's already
fixed upstream.

If something's genuinely missing, build it locally only when it's
app-specific. Anything any BMS app would want (a new nav pattern, a grid
filter widget, a chart type) belongs in `bmsuisse/bmsui` itself
(`packages/ui`/`packages/datagrid`, design rationale in that repo's
`AGENTS.md`) — open a PR there instead of forking it into one app.

## Quick reference

- [ ] Sidebar/nav built from `@bmsuisse/ui`'s `Sidebar`/`SidebarNav`/`NavGroup`/`NavItem`, not hand-rolled
- [ ] Mobile sidebar: `SidebarNav` children reused inside a `Sheet`, not a shrunk `Sidebar`; `100dvh`/safe-area insets for hand-built mobile layouts
- [ ] Grids built from `@bmsuisse/datagrid`'s `DataGrid`/`TreeDataGrid` with `zebra`, not a hand-rolled `<table>`
- [ ] Brand red `#DC001A` used as accent-only or full-primary — pick one, don't mix
- [ ] Backgrounds: 3-tier scale (`--background` → `--card` → `--muted`), not more
- [ ] Border-radius: 6/8/12/16-20/full — no ad hoc values
- [ ] Font: Inter, ~15px base; numbers formatted `de-CH`, tabular numerals outside the grid
- [ ] Icons: `@heroicons/react` (`24/outline`) only, per [`references/icons.md`](references/icons.md) — never hand-drawn
- [ ] `@bmsuisse/ui`/`@bmsuisse/datagrid` current, or a genuinely global gap filed as a PR against `bmsuisse/bmsui` instead of forked locally
