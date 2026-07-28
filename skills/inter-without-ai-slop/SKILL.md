---
name: inter-without-ai-slop
description: Use Inter as a UI typeface in data-dense B2B apps (dashboards, tables, cockpits) without triggering the "generic AI dashboard" look. Trigger when styling a new screen, reviewing an existing one for genericness, or when Inter is already the base face and the app needs to look more considered.
---

# Inter Without the AI-Slop Look

Inter is not the problem. Using it as the *only* typographic decision — one face, one weight for everything, default line-height, default number rendering — is what reads as templated. This skill is a checklist for making Inter feel like a deliberate choice in dense, tabular, internal-tool UIs (sales cockpits, admin panels, ops dashboards).

When reviewing an existing file (not writing one from scratch), run `scripts/audit_ui_file.py <file>` first — it mechanically checks the two things in this checklist that are actually objective (hex colors close to the known AI-default accents, and how many distinct pill/badge shapes a file uses) instead of eyeballing them. It's a heuristic starting point, not a verdict: a flagged color might be an intentional choice (check hue distance and context before asking for a change), and it won't catch anything expressed outside inline hex/className strings (CSS variables, a theme file). Read the file yourself regardless — the script narrows where to look, it doesn't replace looking.

## 1. Split the typographic roles — don't let Inter do everything

A generic-looking screen uses one face for labels, values, headings, and body copy. Give Inter a defined lane and add at least one other face for numbers.

- **Labels / nav / body text:** Inter (Regular/Medium). This is its actual strength — leave it alone here.
- **Numeric data (table columns, KPIs, currency, %):** switch to a monospaced or tabular-figure face — JetBrains Mono, IBM Plex Mono, Berkeley Mono, or Söhne Mono. Numbers that align on a fixed grid read as "someone designed this table."
- **Headings / hero figures (optional):** a face with more character than Inter, used sparingly — one weight, one place. Don't reach for Inter Bold as the only lever for "this matters."

If a second face isn't feasible, at minimum force `font-feature-settings: 'tnum' 1, 'ss01' 1` (tabular figures) on every numeric column so digits don't jitter between rows.

## 2. Ration badges and pills

The single biggest "AI dashboard" tell: every status, tag, trend, and category wrapped in the same rounded-pill shape regardless of semantic weight. Before adding a pill, ask what shape category it belongs to and stay consistent within that category only:

- **Size/type tags** (S/M/L/XL-style): plain small-caps text or a thin underline — not a pill.
- **Genuine alert/risk states:** a pill or filled badge, reserved for cases that need visual interruption.
- **Trend indicators:** icon + colored text, no container at all.
- **Segment/category labels:** consistent pill shape, but one accent family, not a different color per label unless the color itself is meaningful.

If more than ~3 pill styles exist on one screen, that's the tell — consolidate.

## 3. Check the accent color against the known AI-default palette

Three palettes currently cluster as "obviously AI-generated" defaults:
1. Warm cream background + serif display + terracotta/clay accent near `#D97757`
2. Near-black background + single acid-green or vermilion accent
3. Broadsheet layout: hairline rules, zero border-radius, dense newspaper columns

If your brand accent lands within ~15–20° of that terracotta on the color wheel, shift it. It doesn't matter if it's coincidental — it reads as the tell regardless of intent. Anchor the accent to something brand-specific (a real product/company color) rather than a generic "warm CTA" choice.

## 4. Build hierarchy on weight + size, not color alone

Generic dashboards lean entirely on green/red/orange to signal importance. Add a second axis:
- Use Inter's actual weight steps deliberately (500 / 600 / 700) tied to information hierarchy, not decoration.
- Reserve color for state (good/bad/warning), and use weight/size for structural importance (what's the primary number in this card vs. supporting metadata).
- This also fixes accessibility: color-only encoding fails colorblind users and any black/white export (PDF, print).

## 5. Don't "clean up" density that the audience actually needs

For internal power-user tools (sales reps, ops teams, analysts), dense rows and tight spacing are correct, not a flaw to fix toward marketing-site whitespace. The AI-slop instinct is to add breathing room everywhere by default. Resist that here — lean into density, and spend the polish budget on alignment, tabular numbers, and badge discipline instead of adding padding.

## 6. Quick self-audit before shipping

- [ ] Do numeric columns use tabular figures or a dedicated mono face?
- [ ] Are there more than 3 distinct pill/badge shapes on one screen? (should be no)
- [ ] Does the accent color sit close to `#D97757` or acid-green-on-black? (should be no)
- [ ] Is hierarchy legible in grayscale (weight/size), not just color?
- [ ] Is Inter used for labels/nav/body only, or is it also carrying numbers and headings unmodified?
- [ ] Does spacing match the audience (dense for power tools, generous for marketing), rather than a default whitespace template?

## Net result

Inter stays as the quiet, correct choice for UI text — that's its job. The "considered, not generated" signal comes from everything *around* it: a second face for numbers, rationed badges, a brand-true accent, weight-driven hierarchy, and density that matches the actual user.
