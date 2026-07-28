---
name: bms-frontend-design
plugin: coding
description: >
  The BMS visual identity for internal web apps — left navigation layout,
  BMS red accent color, background/surface scale, border-radius scale, a
  minimal zebra-striping pattern for data grids, and the Heroicons
  `24/outline` icon set with a curated concept-to-icon mapping. Use this
  whenever scaffolding a new internal BMS app's UI, building or restyling a
  sidebar/nav, picking
  colors for a new app, styling a data table or grid, choosing icons, or
  reviewing frontend code for visual consistency with other BMS apps. Trigger
  on requests like "make this look like our other internal tools", "add a
  sidebar nav", "what colors should I use", "style this table", "what icon
  should I use for X", or "set up the theme" for a BMS app — even if the user
  doesn't say "design system" explicitly. Supersedes
  generic frontend-aesthetic advice (e.g. "pick a bold, unique look per app")
  for anything under the BMS brand — the point here is consistency across
  apps, not differentiation.
---

# BMS Frontend Design

Concrete, reusable visual conventions for BMS internal web apps, extracted
from two production codebases (OneSales, CCMT2). Unlike generic "make it look
distinctive" advice, the goal here is the opposite: every internal BMS app
should feel like it belongs to the same family. Apply these values directly —
don't reinvent a new palette or radius scale per app.

This assumes a Tailwind v4 + shadcn/ui setup (CSS variables consumed via
`@theme inline`, `bg-background`/`text-foreground`-style utilities, a `.dark`
class variant) — the same setup `init-app-stack` scaffolds. Define the
variables below in `src/index.css` alongside the generated shadcn tokens
rather than hardcoding hex values in components; that's what makes dark mode
and future rebrands (a different `--primary`) work for free.

## Layout — left navigation

A resizable sidebar on the left is the default shell for any internal BMS
app with more than a couple of pages.

- Default width **240px**, resizable between **180–420px**, persisted (e.g.
  `localStorage`). Collapses to a **56px** icon-only rail rather than hiding
  entirely — users should always have nav access.
- Sidebar background: near-white, `--sidebar: #fcfcfc`. Border on the right
  edge only, using the app's subtle border token (`--border: #f2f2f2`
  light). Don't add a border-radius or shadow to the sidebar itself — it's a
  flat plane, not a card.
- Nav rows use `rounded-lg` (8px) corners and an 18×18px icon from
  **`@heroicons/react` (`24/outline`)** — see
  [`references/icons.md`](references/icons.md) for the concept-to-component
  mapping and why not to hand-draw icons.
- **Inactive** row: text at 55% opacity of the foreground color, icon in the
  muted-foreground color, icon stroke-width 1.75. This keeps the resting
  state quiet so the active item reads clearly.
- **Hover** (inactive rows): muted background at 60% opacity — a hint, not a
  highlight.
- **Active** row: full-opacity text + `font-semibold`, background = the
  brand accent at **8% tint** (`bg-nav-primary/8`), icon colored with the
  brand accent, stroke-width 2. The 8% tint is deliberately subtle — this is
  not a filled pill, just enough wash to draw the eye.
- Section group labels (e.g. "Work", "Tools", "Info"): 11px, medium weight,
  muted-foreground at 80% opacity, with a collapse chevron per group.

```css
--sidebar: #fcfcfc;
--nav-primary: #DC001A; /* BMS red — see Brand colors below */
```

```tsx
// active nav item
className="rounded-lg font-semibold text-foreground bg-nav-primary/8"
// icon: className="h-[18px] w-[18px] text-nav-primary" strokeWidth={2}

// inactive nav item
className="rounded-lg text-foreground/55 hover:bg-muted/60 hover:text-foreground"
// icon: className="h-[18px] w-[18px] text-muted-foreground" strokeWidth={1.75}
```

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
never a hardcoded hex in a component — that's what lets dark mode and future
brand variants work without a find-and-replace.

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
once a codebase has been through a few redesigns. Three tiers is enough to
express elevation and easier for every contributor to reason about.

| Tier | Use for | Light | Dark |
|---|---|---|---|
| `--background` | Page/app shell | `#fcfcfc` (near-white) | `oklch(0.165 0.022 265)` |
| `--card` | Cards, panels, modals | `oklch(1 0 0)` (pure white) | `oklch(0.205 0.026 265)` |
| `--muted` | Chips, table headers, subtle fills | `oklch(0.975 0.002 250)` | `oklch(0.245 0.030 265)` |

Note that cards are *whiter* than the page background in light mode — that
subtle lift is what makes a card read as elevated without needing a shadow.

## Border-radius scale

Use one consistent scale everywhere instead of picking a radius per
component. Source material had three competing `--radius` definitions in
the same file — avoid repeating that:

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
  (`font-variant-numeric: tabular-nums`) so digits align in columns.
- Small "eyebrow" labels (section headers, table column meta): ~10–11px,
  bold/semibold, wide letter-spacing (~0.1–0.12em), often uppercase.

## Data grids — minimal zebra

A very subtle alternating-row treatment, not a classic high-contrast zebra
table.

- Stripe alternating rows with the theme's **foreground/text color at 5%
  opacity** (e.g. Tailwind's `bg-foreground/5`) — never a hardcoded gray
  hex. Deriving the stripe from the foreground token means it automatically
  adapts to dark mode without a separate dark-mode override.
- **If the grid is virtualized** (e.g. TanStack Virtual, only visible rows
  exist in the DOM), do not stripe with CSS `:nth-child`/`even:` selectors —
  that stripes by DOM position, which visibly flickers as rows mount/unmount
  during scroll. Key the stripe off the logical row index instead
  (`row.index % 2 === 1`), not DOM position.
- Row hover: the theme's accent color at 50% opacity (`hover:bg-accent/50`),
  layered on top of the stripe.
- Wrap the whole table in a single `rounded-md` (~10px) bordered container —
  no per-cell borders.
- Row separators: a single bottom border per row (the theme's subtle border
  token) — no vertical/left/right borders.
- Header row: slightly muted background (`bg-muted`), often sticky to the
  top of the scroll container.
- Cell padding: compact, ~8px (`p-2`), small text size.

```tsx
className={cn(
  "border-b p-2 text-sm",
  isClickable && "cursor-pointer hover:bg-accent/50",
  rowIndex % 2 === 1 && "bg-foreground/5",
)}
```

## Quick reference

- [ ] Sidebar: 240px default, 180–420px resizable range, 56px collapsed rail
- [ ] Nav active state: `bg-nav-primary/8` + full-opacity text, not a filled pill
- [ ] Brand red `#DC001A` used as accent-only or full-primary — pick one, don't mix
- [ ] Backgrounds: 3-tier scale (`--background` → `--card` → `--muted`), not more
- [ ] Border-radius: 6/8/12/16-20/full — no ad hoc values
- [ ] Font: Inter, ~15px base, tabular numerals for numbers
- [ ] Grid zebra: `bg-foreground/5` on alternating rows, keyed off logical index if virtualized
- [ ] Icons: `@heroicons/react` (`24/outline`) only, per [`references/icons.md`](references/icons.md) — never hand-drawn, and never `lucide-react` (that's shadcn-internal only)
