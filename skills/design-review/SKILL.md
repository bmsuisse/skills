---
name: design-review
plugin: ui
description: >
  Review a web app or page for visual design quality — layout, spacing,
  typography, colour/contrast, visual hierarchy, component consistency,
  interaction states, and responsive behaviour. Not a UX audit (that checks
  usability/flow) — this checks whether it *looks* professional and polished.
  Works from Playwright screenshots (desktop + mobile, light + dark) and
  produces a severity-ranked findings report. Trigger on "design review",
  "does this look good", "does this look off", "review the design", "check
  the layout", "is this polished", "visual review", "design audit", or as the
  screenshot step of `dev-workflow` for any change with a visual/UI surface.
---

# Design Review

Review a web app or page for visual design quality. This is not a UX audit
(usability, workflow, friction) — it checks whether the design is
**professional, consistent, and polished**: would a design-conscious person
look at this and think "this is well made," or "this looks like a developer
designed it"?

> Adapted from [jezweb/claude-skills](https://github.com/jezweb/claude-skills/tree/main/plugins/frontend/skills/design-review)
> (MIT License, © 2025 Jeremy Dawes). See [`NOTICE`](./NOTICE) for the
> original copyright/license text.

## When to Use

- As the screenshot step of `dev-workflow` (step 6) for any PR that touches UI
- Before showing something to a client or team
- When something "looks off" but you can't pinpoint why
- After building a feature, before calling it done
- Periodic quality check on a shipped product

## Capturing Screenshots

Use Playwright (the `playwright-python` skill, `playwright-cli`, or an MCP
Playwright server — whichever is available) to capture the page/app:

- Prefer a deployed/PR-preview URL over `localhost` if one exists (more
  representative of what a reviewer will actually see).
- Capture at both a desktop width (~1440px) and a mobile width (~390px) —
  most inconsistencies show up at one but not the other.
- If the app supports dark mode, capture both themes — most contrast/visibility
  issues only appear in one.
- Capture full-page screenshots, not just the viewport, so below-the-fold
  content gets reviewed too.

## What to Check

### 1. Layout and Spacing

| Check | Good | Bad |
|-------|------|-----|
| **Consistent spacing** | Same gap between all cards in a grid, same padding in all sections | Some cards have 16px gap, others 24px. Header padding differs from body |
| **Alignment** | Left edges of content align vertically across sections | Heading starts at one indent, body text at another, cards at a third |
| **Breathing room** | Generous whitespace around content, elements don't feel cramped | Text touching container edges, buttons crowded against inputs |
| **Grid discipline** | Content follows a clear column grid | Elements placed freely, no underlying structure |
| **Responsive proportions** | Sidebar/content ratio looks intentional at every width | Sidebar takes 50% on tablet, content is squeezed |
| **Vertical rhythm** | Consistent vertical spacing pattern (e.g. 8px/16px/24px/32px scale) | Random spacing: 13px here, 27px there, 8px somewhere else |

### 2. Typography

| Check | Good | Bad |
|-------|------|-----|
| **Hierarchy** | Clear visual difference between h1 → h2 → h3 → body | Headings and body text look the same size/weight |
| **Line length** | Body text 50-75 characters per line | Full-width text running 150+ characters — hard to read |
| **Line height** | Body text 1.5-1.7, headings 1.1-1.3 | Cramped text or excessive line height |
| **Font sizes** | Consistent scale (e.g. 14/16/20/24/32) | Random sizes: 15px, 17px, 22px with no relationship |
| **Weight usage** | Regular for body, medium for labels, semibold for headings, bold sparingly | Everything bold, or everything regular with no hierarchy |
| **Truncation** | Long text truncates with ellipsis, title attribute shows full text | Text overflows container, wraps awkwardly, or is cut off without ellipsis |

### 3. Colour and Contrast

| Check | Good | Bad |
|-------|------|-----|
| **Semantic colour** | Using design tokens (`bg-primary`, `text-muted-foreground`) | Raw palette colours (`bg-blue-500`, `text-gray-300`) hardcoded |
| **Contrast ratio** | Text meets WCAG AA (4.5:1 body, 3:1 large text) | Light grey text on white, or dark text on dark backgrounds |
| **Colour consistency** | Same colour means the same thing everywhere (primary = action) | Blue means "clickable" in one place and "informational" in another |
| **Dark mode** | All elements visible, borders defined, no invisible text | Elements disappear, text becomes unreadable, images look wrong |
| **Status colours** | Green=success, yellow=warning, red=error consistently | Green used for both success and "active" with different meanings |
| **Colour overuse** | 2-3 colours + neutrals | Rainbow of colours with no clear hierarchy |

### 4. Visual Hierarchy

| Check | Good | Bad |
|-------|------|-----|
| **Primary action** | One clear CTA per page, visually dominant | Three equally styled buttons competing for attention |
| **Squint test** | Squinting at the page, the most important element stands out | Everything is the same visual weight — nothing draws the eye |
| **Progressive disclosure** | Most important info visible, details available on interaction | Everything shown at once — overwhelming |
| **Grouping** | Related items are visually grouped (proximity, borders, backgrounds) | Related items scattered, unrelated items touching |
| **Negative space** | Intentional empty space that frames content | Empty space that looks accidental (uneven, trapped white space) |

### 5. Component Consistency

| Check | Good | Bad |
|-------|------|-----|
| **Button styles** | One primary style, one secondary, one destructive — used consistently | 5 different button styles across the app |
| **Card styles** | All cards have the same border-radius, shadow, padding | Some cards rounded, some sharp, some with shadows, some without |
| **Form inputs** | All inputs same height, same border style, same focus ring | Mix of heights, border styles, focus behaviours |
| **Icon style** | One icon family, consistent size and stroke | Mixed icon families, different sizes, some filled some outlined |
| **Border radius** | Consistent radius scale (e.g. 4px inputs, 8px cards, 12px modals) | Random radius values: 3px, 7px, 10px, 16px |
| **Shadow** | One or two shadow levels used consistently | Every component has a different shadow depth |

### 6. Interaction Design

| Check | Good | Bad |
|-------|------|-----|
| **Hover states** | Buttons, links, and clickable cards change on hover | No hover feedback — user unsure what's clickable |
| **Focus states** | Keyboard focus visible on all interactive elements | Focus ring missing or invisible against background |
| **Active states** | Nav items, tabs, sidebar links show current selection | Active item looks the same as inactive |
| **Transitions** | Subtle transitions on hover/focus (150-200ms ease) | No transitions (jarring) or slow transitions (laggy) |
| **Loading indicators** | Skeleton screens or spinners during async operations | Content pops in without warning, layout shifts |
| **Disabled states** | Disabled elements are visually muted, cursor changes | Disabled buttons look clickable, no cursor change |

### 7. Responsive Quality

| Check | Good | Bad |
|-------|------|-----|
| **Mobile nav** | Clean hamburger/sheet menu, easy to tap | Desktop nav squished into mobile, tiny tap targets |
| **Image scaling** | Images fill containers proportionally | Images stretched, cropped badly, or overflowing |
| **Table responsiveness** | Horizontal scroll on mobile, or stack to cards | Table wider than screen with no way to see columns |
| **Touch targets** | At least 44x44px on mobile | Tiny links, close buttons, checkboxes |
| **Tablet** | Layout works at 768px (not just desktop and phone) | Layout breaks at tablet widths, awkward gaps |

If reviewing a BMS internal app, also check against the concrete values in
the `bms-frontend-design` skill (sidebar width, radius scale, brand colours,
zebra-striping) rather than just generic good/bad judgement.

## Severity Guide

| Level | Meaning | Example |
|-------|---------|---------|
| **High** | Looks broken or unprofessional | Invisible text in dark mode, buttons different heights inline |
| **Medium** | Looks unpolished | Inconsistent spacing, mixed icon styles, truncation without ellipsis |
| **Low** | Nitpick | 1-2px alignment, slightly different border-radius, shadow too strong |

## Output

Produce a findings report and attach the screenshots that show each issue:

```markdown
# Design Review: [App/Page Name]
**Date**: YYYY-MM-DD
**URL**: [url]

## Overall Impression
[1-2 sentences — professional / unpolished / inconsistent / clean]

## Findings

### High
- **[issue]** at [page/component] — [what's wrong] → [fix]

### Medium
- **[issue]** at [page/component] — [what's wrong] → [fix]

### Low
- **[issue]** — [description]

## What Looks Good
[Patterns that are well-executed and should be preserved]

## Top 3 Fixes
1. [highest visual impact change]
2. [second]
3. [third]
```

When run as part of `dev-workflow`, attach the report and the flagged
screenshots to the PR (Azure DevOps) instead of writing them to a local-only
file — that's what a reviewer will actually see.

## Tips

- Check dark mode AND light mode — most issues appear in one but not the other
- The squint test is the fastest way to find hierarchy problems
- Component inconsistency is the most common issue in dev-built UIs
- "Looks off" usually means spacing — check margins and padding first
- If you can't identify the issue, compare to a well-designed app in the same category
